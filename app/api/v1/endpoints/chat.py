"""Tenant-scoped internal messaging API; no cross-agency or file workflows."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import ActiveAgencyDep, PrincipalDep, SessionDep
from app.models.chat import ChatConversation, ChatMembership, ChatMessage
from app.models.agency_network import AgencyMembership
from app.models.enums import LEGACY_SOURCE_ALIASES, PropertySource, PropertyStatus
from app.models.property import Property
from app.models.agency_network import Agency
from app.schemas.chat import (
    ChatConversationCreate,
    ChatConversationRead,
    ChatMemberRead,
    ChatMessageCreate,
    ChatMessageRead,
)

router = APIRouter()
logger = logging.getLogger("app.api.chat")


def _identity(principal: PrincipalDep, workspace_id: str | None = None) -> tuple[str, str]:
    tenant, subject = (workspace_id or principal.tenant_id or "").strip(), principal.subject.strip()
    if not tenant or not subject:
        raise HTTPException(403, detail={"error": "chat_identity_unavailable"})
    if not principal.is_verified:
        raise HTTPException(403, detail={"error": "chat_identity_unverified"})
    return tenant, subject


async def _require_chat_membership(
    session: SessionDep, conversation_id: uuid.UUID, tenant: str, subject: str
) -> ChatConversation:
    conversation = await session.get(ChatConversation, conversation_id)
    if conversation is None or conversation.tenant_id != tenant:
        raise HTTPException(404, detail={"error": "conversation_not_found"})
    member = (await session.exec(select(ChatMembership.id).where(
        ChatMembership.conversation_id == conversation_id,
        ChatMembership.tenant_id == tenant,
        ChatMembership.user_subject == subject,
        ChatMembership.left_at.is_(None),
    ))).first()
    if member is None:
        raise HTTPException(404, detail={"error": "conversation_not_found"})
    return conversation


async def _membership(
    session: SessionDep, conversation_id: uuid.UUID, tenant: str, subject: str
) -> ChatConversation:
    result = await session.execute(select(ChatConversation).where(
        ChatConversation.id == conversation_id,
        ChatConversation.tenant_id == tenant,
    ))
    conversation = result.scalars().first()
    if conversation is None:
        raise HTTPException(404, detail={"error": "conversation_not_found"})
    member = (await session.exec(select(ChatMembership.id).where(
        ChatMembership.conversation_id == conversation_id,
        ChatMembership.tenant_id == tenant,
        ChatMembership.user_subject == subject,
        ChatMembership.left_at.is_(None),
    ))).first()
    if member is None:
        raise HTTPException(404, detail={"error": "conversation_not_found"})
    return conversation


async def _read_conversations(
    session: SessionDep, rows: list[ChatConversation]
) -> list[ChatConversationRead]:
    """Build list responses using bounded queries rather than per-room queries."""
    if not rows:
        return []
    conversation_ids = [row.id for row in rows]
    tenant_ids = {row.tenant_id for row in rows}
    if len(tenant_ids) != 1:
        # Admin can see multiple tenants; bulk-read each tenant set separately
        # so no tenant's memberships/messages can enter another room's result.
        by_tenant: dict[str, list[ChatConversation]] = {}
        for row in rows:
            by_tenant.setdefault(row.tenant_id, []).append(row)
        result: list[ChatConversationRead] = []
        for tenant_rows in by_tenant.values():
            result.extend(await _read_conversations(session, tenant_rows))
        return result
    members = (await session.execute(select(ChatMembership).where(
        ChatMembership.conversation_id.in_(conversation_ids),
        ChatMembership.tenant_id == rows[0].tenant_id,
        ChatMembership.left_at.is_(None),
    ).order_by(ChatMembership.joined_at))).scalars().all()
    latest_messages = (await session.execute(
        select(ChatMessage).where(
            ChatMessage.conversation_id.in_(conversation_ids),
            ChatMessage.tenant_id == rows[0].tenant_id,
        ).order_by(ChatMessage.sequence.desc())
    )).scalars().all()
    latest_by_conversation: dict[uuid.UUID, ChatMessage] = {}
    for message in latest_messages:
        existing = latest_by_conversation.get(message.conversation_id)
        if existing is None or message.sequence > existing.sequence:
            latest_by_conversation[message.conversation_id] = message
    members_by_conversation: dict[uuid.UUID, list[ChatMembership]] = {}
    for member in members:
        members_by_conversation.setdefault(member.conversation_id, []).append(member)
    return [
        ChatConversationRead(
            id=row.id,
            title=row.title,
            created_by_subject=row.created_by_subject,
            created_at=row.created_at,
            members=[
                ChatMemberRead(subject=m.user_subject, display_name=m.user_subject)
                for m in members_by_conversation.get(row.id, [])
            ],
            last_message=(
                ChatMessageRead.model_validate(latest_by_conversation[row.id])
                if row.id in latest_by_conversation else None
            ),
        )
        for row in rows
    ]


def _is_chat_admin(principal: PrincipalDep) -> bool:
    return "ROLE_ADMIN" in principal.realm_roles


@router.post("/properties/{property_id}/conversation", response_model=ChatConversationRead, status_code=201)
async def create_property_conversation(
    property_id: uuid.UUID,
    session: SessionDep,
    principal: PrincipalDep,
    active: ActiveAgencyDep,
) -> ChatConversationRead:
    """Open/reuse a conversation only for a live internal listing/account."""
    if _is_chat_admin(principal):
        raise HTTPException(403, detail={"error": "chat_admin_create_forbidden"})
    scoped, _membership, agency = active
    tenant, requester = _identity(scoped, str(agency.id))
    prop = await session.get(Property, property_id)
    if prop is None or prop.status is not PropertyStatus.ACTIVE:
        raise HTTPException(404, detail={"error": "property_not_available"})
    source = LEGACY_SOURCE_ALIASES.get(prop.source, prop.source)
    if source not in {PropertySource.INTERNAL_USER, PropertySource.INTERNAL_AGENCY}:
        raise HTTPException(409, detail={
            "error": "external_listing_no_chat",
            "message": "این آگهی از یک منبع بیرونی دریافت شده و آگهی‌دهنده در سامانه شکارچی حساب ندارد؛ ارسال پیام درون‌برنامه‌ای ممکن نیست.",
        })
    owner = (prop.owner_subject or "").strip()
    if not owner:
        raise HTTPException(409, detail={
            "error": "listing_owner_unavailable",
            "message": "حساب آگهی‌دهنده برای این آگهی در دسترس نیست؛ ارسال پیام ممکن نیست.",
        })
    if requester == owner:
        raise HTTPException(409, detail={"error": "self_message_forbidden", "message": "ارسال پیام به خودتان مجاز نیست."})
    if prop.agency_id is not None and prop.agency_id != agency.id:
        raise HTTPException(404, detail={"error": "property_not_available"})
    owner_membership = (await session.exec(select(AgencyMembership.id).where(
        AgencyMembership.agency_id == agency.id,
        AgencyMembership.user_subject == owner,
        AgencyMembership.revoked_at.is_(None),
    ))).first()
    if owner_membership is None:
        raise HTTPException(409, detail={
            "error": "listing_owner_unavailable",
            "message": "حساب فعال آگهی‌دهنده برای این آگهی پیدا نشد؛ ارسال پیام ممکن نیست.",
        })

    existing = (await session.exec(select(ChatConversation).where(
        ChatConversation.property_id == property_id,
        ChatConversation.tenant_id == tenant,
        ChatConversation.requester_subject == requester,
        ChatConversation.owner_subject == owner,
    ))).first()
    if existing is not None:
        return (await _read_conversations(session, [existing]))[0]

    conversation = ChatConversation(
        tenant_id=tenant,
        property_id=property_id,
        requester_subject=requester,
        owner_subject=owner,
        title=(prop.title or "گفت‌وگوی آگهی")[:160],
        created_by_subject=requester,
    )
    session.add(conversation)
    await session.flush()
    session.add_all([
        ChatMembership(conversation_id=conversation.id, tenant_id=tenant, user_subject=requester),
        ChatMembership(conversation_id=conversation.id, tenant_id=tenant, user_subject=owner),
    ])
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        existing = (await session.exec(select(ChatConversation).where(
            ChatConversation.property_id == property_id,
            ChatConversation.tenant_id == tenant,
            ChatConversation.requester_subject == requester,
            ChatConversation.owner_subject == owner,
        ))).first()
        if existing is None:
            raise HTTPException(409, detail={"error": "conversation_conflict"})
        return (await _read_conversations(session, [existing]))[0]
    await session.refresh(conversation)
    return (await _read_conversations(session, [conversation]))[0]


@router.post("/conversations", response_model=ChatConversationRead, status_code=201)
async def create_conversation(
    payload: ChatConversationCreate,
    session: SessionDep,
    principal: PrincipalDep,
    active: ActiveAgencyDep,
) -> ChatConversationRead:
    if _is_chat_admin(principal):
        raise HTTPException(403, detail={"error": "chat_admin_create_forbidden"})
    _identity(active[0])
    raise HTTPException(503, detail={"error": "chat_membership_unconfigured"})


@router.get("/conversations", response_model=list[ChatConversationRead])
async def list_conversations(
    session: SessionDep,
    principal: PrincipalDep,
    active: ActiveAgencyDep,
    limit: int = Query(default=50, ge=1, le=100),
) -> list[ChatConversationRead]:
    admin = _is_chat_admin(principal)
    if admin:
        tenant = ""
        result = await session.execute(
            select(ChatConversation)
            .order_by(ChatConversation.created_at.desc())
            .limit(limit)
        )
    else:
        scoped, _, agency = active
        tenant, subject = _identity(scoped, str(agency.id))
        result = await session.execute(
            select(ChatConversation)
            .join(ChatMembership, ChatMembership.conversation_id == ChatConversation.id)
            .where(
                ChatConversation.tenant_id == tenant,
                ChatMembership.tenant_id == tenant,
                ChatMembership.user_subject == subject,
                ChatMembership.left_at.is_(None),
            )
            .order_by(ChatConversation.created_at.desc())
            .limit(limit)
        )
    rows = result.scalars().all()
    return await _read_conversations(session, list(rows))


@router.get("/conversations/{conversation_id}/messages", response_model=list[ChatMessageRead])
async def list_messages(
    conversation_id: uuid.UUID,
    session: SessionDep,
    principal: PrincipalDep,
    active: ActiveAgencyDep,
    before_sequence: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[ChatMessageRead]:
    admin = _is_chat_admin(principal)
    if admin:
        conversation = await session.get(ChatConversation, conversation_id)
        if conversation is None:
            raise HTTPException(404, detail={"error": "conversation_not_found"})
        tenant = conversation.tenant_id
    else:
        tenant, subject = _identity(active[0], str(active[2].id))
        await _membership(session, conversation_id, tenant, subject)
    query = select(ChatMessage).where(
        ChatMessage.conversation_id == conversation_id,
        ChatMessage.tenant_id == tenant,
    )
    if before_sequence is not None:
        query = query.where(ChatMessage.sequence < before_sequence)
    result = await session.execute(query.order_by(ChatMessage.sequence.desc()).limit(limit))
    rows = list(result.scalars().all())
    return [ChatMessageRead.model_validate(row) for row in reversed(rows)]


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=ChatMessageRead,
    status_code=201,
)
async def send_message(
    conversation_id: uuid.UUID,
    payload: ChatMessageCreate,
    session: SessionDep,
    principal: PrincipalDep,
    active: ActiveAgencyDep,
) -> ChatMessageRead:
    if _is_chat_admin(principal):
        raise HTTPException(403, detail={"error": "chat_admin_send_forbidden"})
    tenant, subject = _identity(active[0], str(active[2].id))
    await _membership(session, conversation_id, tenant, subject)
    body = payload.body.strip()
    if not body:
        raise HTTPException(422, detail={"error": "empty_message"})
    idem = (
        ChatMessage.conversation_id == conversation_id,
        ChatMessage.sender_subject == subject,
        ChatMessage.client_message_id == payload.client_message_id,
    )
    try:
        # Serialize sequence and retry allocation across all API workers.
        result = await session.execute(select(ChatConversation).where(
            ChatConversation.id == conversation_id,
            ChatConversation.tenant_id == tenant,
        ).with_for_update())
        conversation = result.scalars().first()
        if conversation is None:
            raise HTTPException(404, detail={"error": "conversation_not_found"})
        member = (await session.exec(select(ChatMembership.id).where(
            ChatMembership.conversation_id == conversation_id,
            ChatMembership.tenant_id == tenant,
            ChatMembership.user_subject == subject,
            ChatMembership.left_at.is_(None),
        ))).first()
        if member is None:
            raise HTTPException(404, detail={"error": "conversation_not_found"})
        prior = (await session.execute(select(ChatMessage).where(*idem))).scalars().first()
        if prior:
            if prior.body != body:
                raise HTTPException(409, detail={"error": "idempotency_payload_conflict"})
            return ChatMessageRead.model_validate(prior)
        latest = (await session.execute(
            select(ChatMessage.sequence)
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.sequence.desc())
            .limit(1)
        )).scalar_one_or_none()
        message = ChatMessage(
            conversation_id=conversation_id,
            tenant_id=tenant,
            sequence=(latest or 0) + 1,
            sender_subject=subject,
            sender_name=principal.full_name or principal.username or subject,
            client_message_id=payload.client_message_id,
            body=body,
        )
        session.add(message)
        await session.commit()
        await session.refresh(message)
        return ChatMessageRead.model_validate(message)
    except IntegrityError as exc:
        await session.rollback()
        duplicate = (await session.execute(select(ChatMessage).where(*idem))).scalars().first()
        if duplicate and duplicate.body == body:
            return ChatMessageRead.model_validate(duplicate)
        if duplicate:
            raise HTTPException(409, detail={"error": "idempotency_payload_conflict"}) from exc
        logger.warning("chat message integrity failure (%s)", type(exc).__name__)
        raise HTTPException(409, detail={"error": "message_conflict"}) from exc
