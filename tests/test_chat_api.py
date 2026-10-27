"""Tenant and membership isolation for internal chat; SQLite is in-memory only."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from app.api import deps
from app.api.v1.endpoints import chat
from app.core.identity import Principal
from app.models.chat import ChatConversation, ChatMembership, ChatMessage
from app.models.agency_user import AgencyUser
from app.models.agency_network import Agency, AgencyMembership
from app.models.enums import UserRole


def run(coro):
    return asyncio.run(coro)


async def make_client(subject: str, tenant: str, *, membership: bool = True, roles=None):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(lambda conn: ChatConversation.metadata.create_all(
            conn, tables=[Agency.__table__, AgencyMembership.__table__, AgencyUser.__table__, ChatConversation.__table__, ChatMembership.__table__, ChatMessage.__table__]
        ))
    app_session = AsyncSession(engine, expire_on_commit=False, autoflush=False)
    async def get_test_session():
        async with AsyncSession(engine, expire_on_commit=False, autoflush=False) as session:
            yield session

    app_session.add(AgencyUser(username=subject, full_name=subject, password_hash="", agency_id=tenant))
    workspace_id = uuid.UUID(int=1) if tenant == "office-a" else uuid.UUID(int=2)
    app_session.add(Agency(
        id=workspace_id, slug=tenant, name=tenant, status="VERIFIED",
        referral_code=f"ref-{tenant}",
    ))
    app_session.add(AgencyMembership(
        agency_id=workspace_id, user_subject=subject,
        role="FOUNDER", created_by_subject=subject,
    ))
    await app_session.flush()
    workspace_tenant = str(workspace_id)
    conversation = ChatConversation(tenant_id=workspace_tenant, title="داخلی", created_by_subject="alice")
    app_session.add(conversation)
    await app_session.flush()
    if membership:
        app_session.add(ChatMembership(
            conversation_id=conversation.id, tenant_id=workspace_tenant, user_subject=subject
        ))
    app_session.add(ChatMessage(
        conversation_id=conversation.id, tenant_id=workspace_tenant, sequence=1,
        sender_subject=subject, sender_name=subject, client_message_id=uuid.uuid4(), body="سلام",
    ))
    await app_session.commit()
    await app_session.close()

    app = FastAPI()
    app.include_router(chat.router, prefix="/chat")
    app.dependency_overrides[deps.get_session] = get_test_session
    async def active_workspace():
        subject_override = app.dependency_overrides[deps.get_principal]()
        agency_id = uuid.UUID(subject_override.tenant_id) if subject_override.tenant_id and len(subject_override.tenant_id) == 36 else workspace_id
        agency = await app_session.get(Agency, agency_id)
        async with AsyncSession(engine, expire_on_commit=False) as session:
            membership_row = (await session.exec(select(AgencyMembership).where(
                AgencyMembership.agency_id == agency_id,
                AgencyMembership.user_subject == subject_override.subject,
                AgencyMembership.revoked_at.is_(None),
            ))).first()
        if agency is None or membership_row is None:
            from fastapi import HTTPException
            raise HTTPException(403, detail={"error": "workspace_membership_required"})
        scoped = Principal(
            subject=subject_override.subject, tenant_id=str(agency.id),
            username=subject_override.username, full_name=subject_override.full_name,
            realm_roles=subject_override.realm_roles, roles=subject_override.roles,
            kyc_status=subject_override.kyc_status,
        )
        return scoped, membership_row, agency

    app.dependency_overrides[deps.get_active_agency_membership] = active_workspace
    app.dependency_overrides[deps.get_principal] = lambda: Principal(
        subject=subject, tenant_id=workspace_tenant, username=subject, full_name=subject,
        realm_roles=frozenset(roles or {"ROLE_SENIOR_BROKER"}), roles=frozenset({UserRole.AGENT}),
        kyc_status="VERIFIED",
    )
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    conversation_id = conversation.id
    return client, engine, conversation_id


def test_member_can_read_history_and_send_idempotently():
    async def scenario():
        client, engine, conversation_id = await make_client("alice", "office-a")
        async with client:
            history = await client.get(f"/chat/conversations/{conversation_id}/messages")
            assert history.status_code == 200
            assert [row["sequence"] for row in history.json()] == [1]

            key = str(uuid.uuid4())
            payload = {"client_message_id": key, "body": "  پیام واقعی  "}
            first = await client.post(f"/chat/conversations/{conversation_id}/messages", json=payload)
            assert first.status_code == 201, first.text
            retry = await client.post(f"/chat/conversations/{conversation_id}/messages", json=payload)
            assert first.status_code == retry.status_code == 201
            first_body = first.json()
            retry_body = retry.json()
            assert {**first_body, "created_at": retry_body["created_at"]} == retry_body
            assert first_body["id"] == retry_body["id"]
            assert first_body["sequence"] == 2
        await engine.dispose()

    run(scenario())


def test_non_member_and_other_tenant_get_not_found():
    async def scenario():
        client, engine, conversation_id = await make_client("alice", "office-a")
        override = client._transport.app.dependency_overrides[deps.get_principal]
        client._transport.app.dependency_overrides[deps.get_principal] = lambda: Principal(
            subject="mallory", tenant_id="office-b", username="mallory",
            realm_roles=frozenset({"ROLE_SENIOR_BROKER"}), roles=frozenset({UserRole.AGENT}),
            kyc_status="VERIFIED",
        )
        async with client:
            response = await client.get(f"/chat/conversations/{conversation_id}/messages")
            assert response.status_code == 403
            assert response.json()["detail"]["error"] == "workspace_membership_required"
        client._transport.app.dependency_overrides[deps.get_principal] = override
        await engine.dispose()

    run(scenario())


def test_unconfigured_membership_directory_fails_closed():
    async def scenario():
        client, engine, _ = await make_client("alice", "office-a")
        async with client:
            response = await client.post("/chat/conversations", json={"title": "", "member_subjects": ["bob"]})
            assert response.status_code == 503
            assert response.json()["detail"]["error"] == "chat_membership_unconfigured"
        await engine.dispose()

    run(scenario())


def test_admin_can_read_any_tenant_chat_but_cannot_send_or_create():
    async def scenario():
        client, engine, conversation_id = await make_client(
            "root-admin", "office-a", roles={"ROLE_ADMIN"}
        )
        async with client:
            listed = await client.get("/chat/conversations")
            history = await client.get(f"/chat/conversations/{conversation_id}/messages")
            assert listed.status_code == 200
            assert len(listed.json()) == 1
            assert history.status_code == 200
            assert [message["body"] for message in history.json()] == ["سلام"]

            sent = await client.post(
                f"/chat/conversations/{conversation_id}/messages",
                json={"client_message_id": str(uuid.uuid4()), "body": "admin"},
            )
            created = await client.post(
                "/chat/conversations", json={"title": "admin", "member_subjects": ["alice"]}
            )
            assert sent.status_code == 403
            assert sent.json()["detail"]["error"] == "chat_admin_send_forbidden"
            assert created.status_code == 403
            assert created.json()["detail"]["error"] == "chat_admin_create_forbidden"
        await engine.dispose()

    run(scenario())


def test_idempotency_key_reuse_with_different_body_conflicts():
    async def scenario():
        client, engine, conversation_id = await make_client("alice", "office-a")
        key = str(uuid.uuid4())
        async with client:
            first = await client.post(
                f"/chat/conversations/{conversation_id}/messages",
                json={"client_message_id": key, "body": "اول"},
            )
            conflict = await client.post(
                f"/chat/conversations/{conversation_id}/messages",
                json={"client_message_id": key, "body": "دوم"},
            )
            assert first.status_code == 201
            assert conflict.status_code == 409
            assert conflict.json()["detail"]["error"] == "idempotency_payload_conflict"
        await engine.dispose()

    run(scenario())


def test_left_member_cannot_read_or_send():
    async def scenario():
        client, engine, conversation_id = await make_client("alice", "office-a")
        async with engine.begin() as connection:
            from sqlalchemy import update

            await connection.execute(
                update(ChatMembership)
                .where(ChatMembership.conversation_id == conversation_id)
                .values(left_at=datetime.now(timezone.utc))
            )
        async with client:
            read = await client.get(f"/chat/conversations/{conversation_id}/messages")
            send = await client.post(
                f"/chat/conversations/{conversation_id}/messages",
                json={"client_message_id": str(uuid.uuid4()), "body": "نباید ارسال شود"},
            )
            assert read.status_code == send.status_code == 404
        await engine.dispose()

    run(scenario())


def test_message_listing_has_stable_order_and_cursor():
    async def scenario():
        client, engine, conversation_id = await make_client("alice", "office-a")
        async with client:
            for body in ("دوم", "سوم"):
                response = await client.post(
                    f"/chat/conversations/{conversation_id}/messages",
                    json={"client_message_id": str(uuid.uuid4()), "body": body},
                )
                assert response.status_code == 201
            history = await client.get(f"/chat/conversations/{conversation_id}/messages")
            assert [message["sequence"] for message in history.json()] == [1, 2, 3]
            older = await client.get(
                f"/chat/conversations/{conversation_id}/messages?before_sequence=3"
            )
            assert [message["sequence"] for message in older.json()] == [1, 2]
        await engine.dispose()

    run(scenario())
