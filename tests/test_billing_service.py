"""Focused safety tests for subscription billing primitives."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from cryptography.fernet import Fernet

from app.core.config import Settings
from app.models.billing import PaymentOrder
from app.models.enums import PaymentEnvironmentMode, PaymentOrderStatus
from app.services import billing


def test_live_payment_requires_owner_verified_configured_sixteen_digit_card() -> None:
    base = Settings(
        payment_encryption_key=Fernet.generate_key().decode(),
        payment_card_number="1234 5678 9012 3456",
        payment_card_configured=True,
        payment_card_owner_verified=True,
    )
    assert billing.payment_is_live(base)
    assert not billing.payment_is_live(base.model_copy(update={"payment_card_owner_verified": False}))
    assert not billing.payment_is_live(base.model_copy(update={"payment_card_number": "1234"}))
    assert not billing.payment_is_live(base.model_copy(update={"payment_card_number": "0000000000000000"}))


def test_public_order_never_exposes_test_card_or_requires_encryption_key() -> None:
    key = Fernet.generate_key().decode()
    settings = Settings(payment_encryption_key=key)
    encrypted = Fernet(key.encode()).encrypt(b"0000000000000000").decode()
    order = PaymentOrder(
        order_number="TEST-1", agency_id="agency-a", user_id="user-a", plan="monthly",
        amount_toman=499000, environment_mode=PaymentEnvironmentMode.TEST, is_test=True,
        card_number_snapshot_encrypted=encrypted, card_last4="0000", card_holder_snapshot="test",
        card_configured_snapshot=False, status=PaymentOrderStatus.AWAITING_TRANSFER,
        created_at=datetime.now(timezone.utc), expires_at=datetime.now(timezone.utc),
    )
    result = billing.payment_order_public(order, settings=settings)
    assert result["card_number"] is None
    assert result["card_last4"] is None
    assert result["test_warning"]

    # Test-mode orders remain renderable even when the key is unavailable.
    without_key = settings.model_copy(update={"payment_encryption_key": ""})
    assert billing.payment_order_public(order, settings=without_key)["card_number"] is None


@pytest.mark.parametrize(
    "data",
    [b"", b"not a receipt", b"%PDF-1.4\ntruncated"],
)
def test_receipt_inspection_rejects_empty_and_malformed_files(data: bytes) -> None:
    with pytest.raises(ValueError):
        billing.inspect_receipt(data)


def test_receipt_inspection_accepts_a_minimal_pdf_signature_and_eof() -> None:
    content_type, extension = billing.inspect_receipt(b"%PDF-1.4\nbody\n%%EOF")
    assert (content_type, extension) == ("application/pdf", ".pdf")