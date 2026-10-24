"""User directory: the Keycloak realm, with a local-table fallback.

The ``/dashboard/users`` screen exists in the starter as a feature-complete
table (server prefetch + React Query + nuqs URL state). It used to be backed by
``mock-api-users`` and then by the local ``agency_user`` table; it is now backed
by the Keycloak realm, because the identity provider -- not this node -- is the
authority on who exists and what tier they hold. A user disabled in Keycloak no
longer keeps an active staff row here.

``agency_user`` remains in use for quota accounting and audit rows, which have
no business living in an external IdP.

When no Keycloak service account is configured the router falls back to
``agency_user``, so a fresh clone works before Keycloak is ever started.

Authorisation is unchanged: any staff may list the directory, but only
OFFICE_MANAGER / ADMIN may mutate staff -- a junior broker inviting a new peer
would be a privilege-escalation path.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func
from sqlmodel import select

from app.api.deps import PrincipalDep, SessionDep, SettingsDep
from app.core.security import hash_password
from app.models.agency_user import AgencyUser
from app.models.enums import UserRole
from app.services import keycloak_admin
from app.services.keycloak_admin import DirectoryUser, KeycloakDirectoryError

_ROLE_ORDER = {
    UserRole.GUEST: 0,
    UserRole.USER: 1,
    UserRole.OWNER: 2,
    UserRole.AGENT: 3,
    UserRole.OFFICE_MANAGER: 4,
    UserRole.SUPERVISOR: 5,
    UserRole.ADMIN: 6,
}
from app.schemas.users import UserMutationIn, UserOut, UsersListResponse

logger = logging.getLogger("app.api.v1.users")

router = APIRouter()


def _split_name(full_name: str) -> tuple[str, str]:
    """Best-effort split: first token given, remainder family."""
    parts = (full_name or "").split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def _row_to_out(row: AgencyUser) -> UserOut:
    first, last = _split_name(row.full_name or "")
    status = "ACTIVE" if row.is_active else "INACTIVE"
    email = row.username if "@" in (row.username or "") else ""
    return UserOut(
        id=str(row.id),
        first_name=first,
        last_name=last,
        email=email,
        phone=row.phone or "",
        status=status,
        role=row.role,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _require_manager(principal: PrincipalDep) -> PrincipalDep:
    allowed = {UserRole.OFFICE_MANAGER, UserRole.ADMIN}
    if not (principal.roles & allowed):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "forbidden_role",
                "message": "مدیریت کاربران تنها برای مدیر دفتر یا مدیر سامانه مجاز است.",
            },
        )
    return principal


def _parse_role_filter(roles: str | None) -> set[UserRole]:
    """Turn ``?roles=ADMIN,AGENT`` into the set of tiers to keep."""
    if not roles:
        return set()
    wanted: set[UserRole] = set()
    for raw in roles.split(","):
        name = raw.strip().upper()
        if name in UserRole.__members__:
            wanted.add(UserRole[name])
    return wanted


def _directory_matches(
    user: DirectoryUser, needle: str, wanted_roles: set[UserRole]
) -> bool:
    if wanted_roles and user.role not in wanted_roles:
        return False
    if not needle:
        return True
    haystack = " ".join(
        (user.first_name, user.last_name, user.email, user.phone, user.username)
    ).lower()
    return needle in haystack


def _breakdown(users: list[DirectoryUser]) -> list[dict[str, object]]:
    """Histogram over the *filtered* set.

    Derived from the same list the rows come from, so the counts and the visible
    rows can never disagree.
    """
    counts: dict[UserRole, int] = {}
    for user in users:
        counts[user.role] = counts.get(user.role, 0) + 1
    return [
        {"role": role, "count": counts[role]} for role in sorted(counts, key=_ROLE_ORDER.get)
    ]


def _directory_envelope(
    users: list[DirectoryUser], page: int, limit: int, search: str | None, roles: str | None
) -> UsersListResponse:
    """Paginate the filtered directory into the table's existing envelope."""
    needle = (search or "").strip().lower()
    wanted_roles = _parse_role_filter(roles)

    filtered = [u for u in users if _directory_matches(u, needle, wanted_roles)]
    total = len(filtered)
    offset = (page - 1) * limit
    page_rows = filtered[offset : offset + limit]

    return UsersListResponse(
        time=datetime.now(timezone.utc).isoformat(),
        message="OK",
        total_users=total,
        offset=offset,
        limit=limit,
        users=[UserOut(**keycloak_admin.to_user_out(u)) for u in page_rows],
        role_breakdown=_breakdown(filtered),  # type: ignore[arg-type]
    )


def _raise_keycloak(exc: KeycloakDirectoryError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={"error": exc.code, "message": exc.message},
    )


async def _guard_last_admin(
    settings: SettingsDep,
    user_id: uuid.UUID,
    *,
    new_role: UserRole | None,
    disabling: bool,
) -> None:
    """Refuse to demote or disable the realm's only administrator.

    The last admin is the office's sole path back into the management screens;
    losing it leaves no recovery path short of editing the realm by hand.

    One directory read answers both questions, so the check costs a single
    round trip regardless of how many fields the sheet is changing.
    """
    if not disabling and (new_role is None or new_role is UserRole.ADMIN):
        return

    try:
        directory = await keycloak_admin.list_directory_users(settings)
    except KeycloakDirectoryError as exc:
        raise _raise_keycloak(exc) from exc

    target = next((u for u in directory if u.id == str(user_id)), None)
    if target is None or target.role is not UserRole.ADMIN:
        # Not an admin, or not in the realm: nothing to protect.
        return

    if disabling or new_role is not UserRole.ADMIN:
        remaining = [
            u
            for u in directory
            if u.role is UserRole.ADMIN and u.enabled and u.id != str(user_id)
        ]
        if not remaining:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "last_admin",
                    "message": "نمی‌توان آخرین مدیر سامانه را تنزل یا غیرفعال داد.",
                },
            )


async def _update_directory_user(
    user_id: uuid.UUID,
    body: UserMutationIn,
    settings: SettingsDep,
    principal: PrincipalDep,
) -> UserOut:
    """Apply a profile/tier/status change to a realm user."""
    wants_inactive = body.status.upper() == "INACTIVE" if body.status else None

    await _guard_last_admin(
        settings, user_id, new_role=body.role, disabling=bool(wants_inactive)
    )

    try:
        updated = await keycloak_admin.update_user(
            settings,
            str(user_id),
            email=body.email.strip() or None,
            # An empty name field means "leave it alone": the sheet submits every
            # field, so treating "" as a clear would wipe names on every save.
            first_name=body.first_name if body.first_name else None,
            last_name=body.last_name if body.last_name else None,
            phone=body.phone if body.phone else None,
            role=body.role,
            enabled=None if wants_inactive is None else not wants_inactive,
        )
    except KeycloakDirectoryError as exc:
        raise _raise_keycloak(exc) from exc

    logger.info("keycloak user updated: %s by=%s", updated.email or updated.id, principal.subject)
    return UserOut(**keycloak_admin.to_user_out(updated))


@router.get("", response_model=UsersListResponse)
async def list_users(
    session: SessionDep,
    settings: SettingsDep,
    principal: PrincipalDep,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: str | None = Query(None),
    roles: str | None = Query(None, description="Comma-separated UserRole values"),
) -> UsersListResponse:
    """List staff with the same envelope the starter table consumes."""
    if keycloak_admin.is_directory_enabled(settings):
        try:
            directory = await keycloak_admin.list_directory_users(settings)
        except KeycloakDirectoryError as exc:
            # Falling back would silently show a different directory than the
            # one the IdP holds, so surface the outage instead.
            logger.error("keycloak directory read failed: %s", exc.message)
            raise _raise_keycloak(exc) from exc
        return _directory_envelope(directory, page, limit, search, roles)

    role_filter = {r.strip().upper() for r in roles.split(",")} if roles else set()

    stmt = select(AgencyUser)
    if role_filter:
        valid = [r for r in role_filter if r in UserRole.__members__]
        if valid:
            stmt = stmt.where(AgencyUser.role.in_([UserRole[v] for v in valid]))
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(
            (AgencyUser.full_name.ilike(like))  # type: ignore[union-attr]
            | (AgencyUser.username.ilike(like))  # type: ignore[union-attr]
            | (AgencyUser.phone.ilike(like))  # type: ignore[union-attr]
        )

    total = (await session.exec(select(func.count()).select_from(stmt.subquery()))).one()
    offset = (page - 1) * limit
    rows = (await session.exec(stmt.order_by(AgencyUser.created_at.desc()).offset(offset).limit(limit))).all()

    breakdown_rows = (
        await session.exec(select(AgencyUser.role, func.count()).group_by(AgencyUser.role))
    ).all()
    breakdown = [{"role": role, "count": count} for role, count in breakdown_rows]
    breakdown.sort(key=lambda item: _ROLE_ORDER.get(item["role"], -1))

    return UsersListResponse(
        time=datetime.now(timezone.utc).isoformat(),
        message="OK",
        total_users=int(total),
        offset=offset,
        limit=limit,
        users=[_row_to_out(r) for r in rows],
        role_breakdown=breakdown,  # type: ignore[arg-type]
    )


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserMutationIn,
    session: SessionDep,
    settings: SettingsDep,
    principal: PrincipalDep,
) -> UserOut:
    """Invite a staff member."""
    _require_manager(principal)
    username = (body.email or body.phone or "").strip()
    if not username:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "missing_login", "message": "ایمیل یا شماره تماس برای ورود الزامی است."},
        )

    if keycloak_admin.is_directory_enabled(settings):
        # Keycloak owns the credential, so it needs a real email as the login;
        # a phone-only invite cannot be represented there.
        if not body.email:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "missing_login",
                    "message": "برای دعوت کاربر در Keycloak، ایمیل الزامی است.",
                },
            )
        try:
            created = await keycloak_admin.create_user(
                settings,
                email=body.email.strip(),
                first_name=body.first_name.strip(),
                last_name=body.last_name.strip(),
                phone=body.phone.strip(),
                role=body.role,
                enabled=body.status.upper() != "INACTIVE",
            )
        except KeycloakDirectoryError as exc:
            raise _raise_keycloak(exc) from exc
        logger.info("keycloak user invited: %s by=%s", body.email, principal.subject)
        return UserOut(**keycloak_admin.to_user_out(created))

    existing = (await session.exec(select(AgencyUser).where(AgencyUser.username == username))).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "duplicate_user", "message": "کاربری با این نام کاربری وجود دارد."},
        )
    full_name = f"{body.first_name} {body.last_name}".strip()
    row = AgencyUser(
        username=username,
        full_name=full_name or username,
        phone=(body.phone or "").strip(),
        # Random credential placeholder: the real password is set on first
        # login via the identity provider, never through this row.
        password_hash=hash_password(uuid.uuid4().hex),
        role=body.role,
        is_active=body.status.upper() != "INACTIVE",
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    logger.info("user created: %s role=%s by=%s", username, body.role, principal.subject)
    return _row_to_out(row)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: uuid.UUID,
    body: UserMutationIn,
    session: SessionDep,
    settings: SettingsDep,
    principal: PrincipalDep,
) -> UserOut:
    """Update staff role/status/contact (managers only)."""
    _require_manager(principal)

    if keycloak_admin.is_directory_enabled(settings):
        return await _update_directory_user(user_id, body, settings, principal)

    row = await session.get(AgencyUser, user_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="کاربر یافت نشد.")
    if body.role is not None:
        # A manager may not demote the last ADMIN — the node would lose its
        # privileged account with no recovery path.
        if row.role == UserRole.ADMIN and body.role != UserRole.ADMIN:
            admins = (
                await session.exec(
                    select(func.count())
                    .select_from(AgencyUser)
                    .where(AgencyUser.role == UserRole.ADMIN, AgencyUser.is_active.is_(True))
                )
            ).one()
            if int(admins) <= 1:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"error": "last_admin", "message": "نمی‌توان آخرین مدیر سامانه را تنزل داد."},
                )
        row.role = body.role
    if body.status:
        row.is_active = body.status.upper() != "INACTIVE"
    if body.first_name or body.last_name:
        cur_first, cur_last = _split_name(row.full_name or "")
        row.full_name = f"{body.first_name or cur_first} {body.last_name or cur_last}".strip()
    if body.phone:
        row.phone = body.phone.strip()
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _row_to_out(row)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    session: SessionDep,
    settings: SettingsDep,
    principal: PrincipalDep,
) -> None:
    """Deactivate staff (soft-delete: the audit trail keeps their history)."""
    _require_manager(principal)

    if keycloak_admin.is_directory_enabled(settings):
        # Disabling, not deleting: Keycloak retains the account and its history,
        # which is what the PII audit trail needs to stay readable.
        await _guard_last_admin(settings, user_id, new_role=None, disabling=True)
        try:
            await keycloak_admin.set_enabled(settings, str(user_id), False)
        except KeycloakDirectoryError as exc:
            raise _raise_keycloak(exc) from exc
        logger.info("keycloak user deactivated: %s by=%s", user_id, principal.subject)
        return None

    row = await session.get(AgencyUser, user_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="کاربر یافت نشد.")
    if row.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "cannot_delete_admin", "message": "حذف مدیر سامانه مجاز نیست؛ ابتدا نقش را تغییر دهید."},
        )
    row.is_active = False
    session.add(row)
    await session.commit()
    logger.info("user deactivated: %s by=%s", row.username, principal.subject)
    return None


__all__ = ["router"]
