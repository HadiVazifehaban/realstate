# Footer social links

## Deployment prerequisites

- Apply Alembic revision `a7c2d9e4f610` with the existing migration deployment
  procedure (`alembic upgrade head`) before enabling the new backend/frontend.
- No destinations are seeded. A verified administrator must configure actual
  accounts at `/dashboard/settings/social-links`.
- Management accepts signed Keycloak realm roles `ROLE_ADMIN`,
  `ROLE_SUPER_ADMIN`, `admin`, or `super_admin`, and still requires KYC approval.
  Site-specific aliases do not grant access to other administrative APIs.
- No realm, database, or container is changed by adding these files.

## API (under `/api/v1`)

- `GET /site/social-links`: public, active links only, ordered by `sort_order`
  and UUID. No credentials or account configuration are returned.
- `GET/POST /admin/social-links`: list all / create.
- `PUT /admin/social-links/{id}`: edit all link fields.
- `PATCH /admin/social-links/{id}`: visibility only (`is_active`).
- `DELETE /admin/social-links/{id}`: delete.
- `PUT /admin/social-links/reorder`: `{ "ids": ["uuid", "uuid"] }` must contain
  each current link exactly once. Invalid/stale membership returns 409 and makes
  no changes. Ordering updates are transactional, with PostgreSQL row locks.

HTTP(S) destinations only; credentials, executable schemes, whitespace and
backslashes are rejected. Links are never fetched by the backend. Platform keys
may be custom; icons are limited to the bundled registry (including generic
`link`). Iranian messenger marks are local monochrome SVGs, not remote assets.

## Refresh and failure behavior

Admin switches and reorder update optimistically, roll back on failure, and
invalidate admin/public query caches after completion. Other open pages poll the
public configuration every 60 seconds while active. The footer renders no sample
accounts when configuration is empty or unavailable.

## Verification

Use the repository virtualenv for `pytest -q tests/test_footer_social_links.py`.
Tests use a disposable in-memory SQLite schema and mock only token verification;
authorization, KYC checks, request validation, SQL persistence and HTTP routes run
normally. Production PostgreSQL migration/row-lock behavior needs staging
verification before rollout.