import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.network import (
    _authorize_share,
    _share_agency,
    extend_share,
    get_share,
    list_shares,
    revoke_share,
)
from app.core.identity import Principal
from app.models.enums import ShareStatus
from app.models.network_collab import ListingShare


def principal(agency_id):
    return Principal(subject="broker", tenant_id=str(agency_id) if agency_id else None)


@pytest.fixture
def share():
    return ListingShare(
        property_id=uuid.uuid4(), source_agency_id=uuid.uuid4(),
        target_agency_id=uuid.uuid4(), internal_note="source only",
    )


@pytest.mark.parametrize("tenant", [None, "invalid"])
def test_missing_or_invalid_tenant_fails_closed(tenant):
    with pytest.raises(HTTPException) as error:
        _share_agency(principal(tenant))
    assert error.value.status_code == 403


def test_only_participants_read_and_only_source_manages(share):
    _authorize_share(share, principal(share.source_agency_id), manage=True)
    _authorize_share(share, principal(share.target_agency_id))
    for identity, manage in [(share.target_agency_id, True), (uuid.uuid4(), False)]:
        with pytest.raises(HTTPException) as error:
            _authorize_share(share, principal(identity), manage=manage)
        assert error.value.status_code == 403


async def test_foreign_agency_list_rejected_before_database_access():
    session = AsyncMock()
    with pytest.raises(HTTPException) as error:
        await list_shares(session, None, principal(uuid.uuid4()), agency_id=uuid.uuid4())
    assert error.value.status_code == 403
    session.exec.assert_not_called()


@pytest.mark.parametrize("operation", [revoke_share, extend_share])
async def test_target_cannot_mutate_share(share, operation):
    session = AsyncMock()
    session.get.return_value = share
    with pytest.raises(HTTPException) as error:
        await operation(share.id, session, principal(share.target_agency_id), None)
    assert error.value.status_code == 403
    session.commit.assert_not_called()


async def test_revoked_share_cannot_be_extended(share):
    share.status = ShareStatus.REVOKED
    session = AsyncMock()
    session.get.return_value = share
    with pytest.raises(HTTPException) as error:
        await extend_share(share.id, session, principal(share.source_agency_id), None, days=30)
    assert error.value.status_code == 409
    session.commit.assert_not_called()


async def test_incoming_detail_does_not_expose_internal_note(share):
    session = AsyncMock()
    session.get.side_effect = [share, None]
    detail = await get_share(share.id, session, None, principal(share.target_agency_id))
    assert detail.internal_note == ""


async def test_list_defaults_to_verified_tenant_and_applies_direction(share):
    session = AsyncMock()
    session.exec.return_value = SimpleNamespace(all=lambda: [share])
    result = await list_shares(
        session, None, principal(share.target_agency_id), agency_id=None,
        direction="incoming", status_filter=None, limit=50, offset=50,
    )
    statement = session.exec.call_args.args[0]
    sql = str(statement)
    assert "target_agency_id =" in sql
    assert share.target_agency_id in statement.compile().params.values()
    assert result[0].id == share.id


async def test_source_can_revoke_and_write_audit(share):
    from unittest.mock import Mock

    session = AsyncMock()
    session.add = Mock()
    session.get.return_value = share
    result = await revoke_share(share.id, session, principal(share.source_agency_id), None)
    assert result.status == ShareStatus.REVOKED.value
    session.commit.assert_awaited_once()
    assert session.add.call_count == 2