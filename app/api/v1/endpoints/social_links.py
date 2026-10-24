"""Public active links and explicitly role-gated site configuration."""

import uuid
from typing import Annotated, Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, TypeAdapter, field_validator
from sqlalchemy import select

from app.api.deps import SessionDep, SettingsDep, _bearer_token
from app.core.config import AuthMode
from app.core.identity import IdentityError, Principal, principal_from_token, require_approval
from app.models.footer_social_link import FooterSocialLink

ADMIN_ROLES = frozenset({"ROLE_ADMIN", "ROLE_SUPER_ADMIN", "admin", "super_admin"})
IconName = Literal[
    "youtube", "telegram", "instagram", "linkedin", "eitaa", "rubika", "bale", "soroush", "link"
]


async def require_social_admin(request: Request, settings: SettingsDep) -> None:
    # Use the existing token verifier and approval gate, but do not map site-only
    # admin aliases into the internal role ladder (which would grant other powers).
    if settings.auth_mode is not AuthMode.KEYCLOAK:
        raise HTTPException(status_code=503, detail="Keycloak authentication required")
    token = _bearer_token(request)
    try:
        principal: Principal = await principal_from_token(token, settings)
        require_approval(principal, settings)
    except IdentityError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    if not ADMIN_ROLES.intersection(principal.realm_roles):
        raise HTTPException(status_code=403, detail="دسترسی مدیر لازم است.")


public_router = APIRouter()
admin_router = APIRouter(dependencies=[Depends(require_social_admin)])


class SocialLinkValues(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    platform_key: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_-]*$")
    display_name: str = Field(min_length=1, max_length=100)
    icon_name: IconName
    url: str = Field(min_length=1, max_length=2048)
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0, le=1000000)

    @field_validator("url")
    @classmethod
    def safe_url(cls, value: str) -> str:
        if any(char.isspace() or ord(char) < 32 for char in value) or "\\" in value:
            raise ValueError("A valid HTTP(S) URL is required")
        parsed = TypeAdapter(HttpUrl).validate_python(value)
        if parsed.username or parsed.password or not urlsplit(value).netloc:
            raise ValueError("URL credentials are not allowed")
        return str(parsed)


class SocialLinkOut(SocialLinkValues):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID


class VisibilityIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_active: bool


class ReorderIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ids: Annotated[list[uuid.UUID], Field(min_length=1, max_length=1000)]


async def ordered_links(session: SessionDep, active_only: bool = False):
    statement = select(FooterSocialLink).order_by(FooterSocialLink.sort_order, FooterSocialLink.id)
    if active_only:
        statement = statement.where(FooterSocialLink.is_active.is_(True))
    return list((await session.execute(statement)).scalars().all())


async def get_link(session: SessionDep, link_id: uuid.UUID) -> FooterSocialLink:
    row = await session.get(FooterSocialLink, link_id)
    if row is None:
        raise HTTPException(status_code=404, detail="پیوند پیدا نشد.")
    return row


@public_router.get("/social-links", response_model=list[SocialLinkOut])
async def public_links(session: SessionDep, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return await ordered_links(session, active_only=True)


@admin_router.get("", response_model=list[SocialLinkOut])
async def list_links(session: SessionDep):
    return await ordered_links(session)


@admin_router.post("", response_model=SocialLinkOut, status_code=201)
async def create_link(values: SocialLinkValues, session: SessionDep):
    row = FooterSocialLink(**values.model_dump())
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


@admin_router.put("/reorder", response_model=list[SocialLinkOut])
async def reorder_links(values: ReorderIn, session: SessionDep):
    statement = select(FooterSocialLink).order_by(FooterSocialLink.id).with_for_update()
    rows = list((await session.execute(statement)).scalars())
    if len(set(values.ids)) != len(values.ids) or set(values.ids) != {row.id for row in rows}:
        raise HTTPException(status_code=409, detail="فهرست تغییر کرده است؛ دوباره بارگذاری کنید.")
    positions = {link_id: index for index, link_id in enumerate(values.ids)}
    for row in rows:
        row.sort_order = positions[row.id]
    await session.commit()
    return await ordered_links(session)


@admin_router.put("/{link_id}", response_model=SocialLinkOut)
async def update_link(link_id: uuid.UUID, values: SocialLinkValues, session: SessionDep):
    row = await get_link(session, link_id)
    for key, value in values.model_dump().items():
        setattr(row, key, value)
    await session.commit()
    await session.refresh(row)
    return row


@admin_router.patch("/{link_id}", response_model=SocialLinkOut)
async def toggle_link(link_id: uuid.UUID, values: VisibilityIn, session: SessionDep):
    row = await get_link(session, link_id)
    row.is_active = values.is_active
    await session.commit()
    await session.refresh(row)
    return row


@admin_router.delete("/{link_id}", status_code=204)
async def delete_link(link_id: uuid.UUID, session: SessionDep):
    await session.delete(await get_link(session, link_id))
    await session.commit()
    return Response(status_code=204)