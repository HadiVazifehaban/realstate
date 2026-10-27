from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.api.v1.endpoints.billing import PlanCreateBody


def valid_plan(**overrides):
    values = {
        "title": "Bronze test",
        "description": "test plan",
        "price_toman": 100_000,
        "duration_days": 30,
        "listing_quota": 10,
        "sms_quota": 5,
        "regions_quota": 1,
        "advisor_quota": 2,
        "is_unlimited": False,
        "features": [],
        "is_active": True,
        "sort_order": 10,
    }
    values.update(overrides)
    return values


def test_plan_schema_requires_explicit_unlimited_caps_instead_of_large_sentinel_values():
    unlimited = PlanCreateBody(
        id="gold_custom",
        **valid_plan(listing_quota=None, advisor_quota=None, is_unlimited=True),
    )
    assert unlimited.listing_quota is None
    assert unlimited.advisor_quota is None

    with pytest.raises(ValidationError):
        PlanCreateBody(id="broken_plan", **valid_plan(listing_quota=None, is_unlimited=False))


def test_free_plan_cannot_be_mutated_into_a_paid_plan_or_disabled():
    with pytest.raises(ValidationError):
        PlanCreateBody(id="free", **valid_plan(price_toman=1))
    with pytest.raises(ValidationError):
        PlanCreateBody(id="new_paid", **valid_plan(price_toman=0))
