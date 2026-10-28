# Public Publication Contract — Gate 1 proposal

**Status: proposal only.** No public route is registered, no migration has been
run, and existing rows remain private by default. Product/API owner approval is
required before schema migration or rollout.

## Schema proposal

Keep operational `Property.status` and internal share/workspace permissions
separate from public publication. Add a one-to-one `property_publication` row:

| Column | Type / invariant | Meaning |
|---|---|---|
| `property_id` | UUID PK/FK `property.id`, `ON DELETE CASCADE` | Internal relation only |
| `public_id` | UUID unique, non-null, generated server-side | Opaque public locator; not a capability |
| `consent_status` | enum `NOT_GIVEN/GIVEN/REVOKED` default `NOT_GIVEN` | Explicit owner/authorized representative consent |
| `consent_actor_subject` | nullable string | Authenticated consenting subject (private audit data) |
| `consented_at`, `consent_version` | nullable timestamptz / string | Evidence and exact terms accepted |
| `review_status` | enum `PENDING/APPROVED/REJECTED` default `PENDING` | Human moderation state |
| `reviewed_by_subject`, `reviewed_at`, `review_note_private` | nullable | Reviewer attribution; private note never public |
| `publish_starts_at`, `publish_ends_at` | nullable timestamptz | Half-open interval `[start,end)`; both required to serve, `end > start` |
| `revoked_at`, `revoked_by_subject`, `revocation_reason` | nullable | Immediate publication withdrawal; revocation is terminal until a new consent/review cycle |
| `sanitized_title`, `sanitized_description` | nullable text | Reviewed public copy, distinct from free-form internal source fields |
| `content_reviewed_at`, `content_reviewed_by_subject` | nullable | Review provenance for the sanitized copy |
| `created_at`, `updated_at` | timestamptz | Row lifecycle |

Add `property_media_publication` keyed by `(property_id, media_id)` with
`allow_public=false NOT NULL`, `review_status=PENDING`, reviewer/consent evidence,
and revocation timestamps; FK to both property and media (prefer a composite FK
ensuring the media belongs to that property). The public decision requires the
media row still exists, is attached to the same property, has `allow_public`, is
approved, has a safe MIME type and a servable generated asset. Do not expose
`local_path`, original filenames, private storage URLs, or raw cloud URLs.

Append-only `property_publication_audit` records publication/property/media ID,
event, actor subject, timestamp, request/correlation ID, and minimal before/after
JSON. Do not copy consent secrets, raw PII, exact address or unrestricted source
text into audit payloads. Restrict audit writes to the policy service and reads
to designated internal roles.

Indexes: unique `public_id`; `(review_status,publish_starts_at,publish_ends_at)`;
media `(property_id,allow_public,review_status)`; audit `(publication_id,created_at)`.
All new consent, review and media-allow flags default false/non-approved; no
backfill may infer consent from `ACTIVE`, MLS sharing, a Share, or workspace
visibility.

## Migration plan and rollback

After approval, create enums/tables and constraints in an additive Alembic
revision; do not add public-enabled defaults to `property` or modify old rows.
Deploy code in dark mode with no route and no feature flag enabled. Backfill only
non-sensitive generated public IDs, if needed; publication remains denied because
consent/review/media states remain false. Verify constraints and query plans on a
disposable clone before production approval. This proposal has **not** been
executed. A runnable-but-unapplied Alembic draft is present at
`alembic/versions/1c7e9a2b4d60_publication_contract.py`; review its constraints
and downgrade behavior against the actual schema before approval.

Rollback before any publication data exists: drop audit, media-authorization and
publication tables, then associated enum types, in reverse dependency order.
After data exists, disable the reader first and export/audit the evidence; a
destructive downgrade must refuse to drop non-empty consent/audit history. Never
rollback by resetting the shared Git worktree.

## Lifecycle and permission matrix

1. Draft/internal listing: no publication row or default `NOT_GIVEN/PENDING`; deny.
2. Consent: active owner or explicitly authorized property manager records a
   separate affirmative act and immutable terms/version; deny until review.
3. Moderation: reviewer approves sanitized title/description and each media item;
   reject/hold denies.
4. Schedule: authorized manager sets a future/current start and mandatory future
   end. Reader accepts only `now >= start AND now < end`.
5. Read: central policy checks every condition below on every request (or from a
   cache with revocation-safe invalidation); public ID only locates the row.
6. Revoke/withdraw, block, delete, close transaction, or expire: deny immediately;
   invalidate cached objects/media. New publication requires renewed consent and
   review, preserving prior audit events.

| Actor | Consent | Submit/revise sanitized copy | Approve/reject | Schedule/revoke | Public read |
|---|---:|---:|---:|---:|---:|
| Property owner / explicitly delegated manager | Yes | Yes | No | Request; revoke own consent | No special bypass |
| Workspace broker with property-manage permission | Only if documented delegation | Yes | No | Request/revoke within delegation | No |
| Independent moderator | No | Review/edit decision only | Yes | No | No |
| Internal service identity | Persist evidence and evaluate policy | No implicit consent | No human approval | Enforce revocation/expiry | Enforce policy only |
| Anonymous client | No | No | No | No | Read only after policy allow |

Share permissions and workspace visibility confer no publication right.

## Central fail-closed policy

`can_public_read(property, publication, now)` is true only if every predicate is
proven: property exists, `status == ACTIVE`, not deleted/blocked/closed; explicit
consent is `GIVEN` with actor/time/terms; review is `APPROVED`; sanitized copy
passed content review; start/end are present and `start <= now < end`; no
revocation; and each returned media item independently has explicit public
authorization, approval, non-revocation, safe content type and a public derivative.
Any absent row, NULL, parsing/storage error, inconsistent media-parent relation,
or unknown enum means deny. A missing/invalid public ID must not reveal existence.

## Public DTO allowlist

Independent Pydantic DTO (`extra="forbid"`, no ORM inheritance or
`from_attributes` projection):

```text
public_id, sanitized_title, sanitized_description,
property_type, deal_type, city, neighborhood,
area, rooms, total_price, price_per_meter,
deposit_amount, monthly_rent,
has_elevator, has_parking, has_storage, has_balcony,
approximate_latitude, approximate_longitude, privacy_radius_m,
approved_media[{public_media_id, derivative_url, media_type, sort_order, is_cover}]
```

Never include internal UUIDs, source/reference/code, exact address/coordinates,
owner identity/contact, workspace or agent identity, submission/moderation notes,
raw description, internal statuses, valuation internals, local paths, or audit
fields. Validate/clean the copied public title/description before approval; reject
HTML/script, contact details, personal identifiers, exact address, URLs or
unreviewed location claims. Build DTOs explicitly from this allowlist; test that
adding any internal Property/PropertyMedia field does not change serialized
output. Public ID is an identifier, never authorization.

## Test evidence and remaining Gate 1 work

The policy, DTOs, lifecycle service, model and unapplied migration draft exist,
but no public route is connected. Current tests cover policy predicates and DTO
allowlisting; mutation/IDOR/cross-workspace/media lifecycle integration coverage
is incomplete. Before enabling a reader, confirm consent actor/authority,
moderation staffing, permitted commercial fields, copy moderation rules, public
ID format, expiry defaults, public media delivery/CDN and revocation SLA with the
product/API owner. Add service-level tests for deny-by-default, absent consent,
invalid review, private media, cross-workspace attempts, IDOR, unauthorized
mutation, revocation, expiry and DTO non-leakage before any router is added.

The lifecycle now requires the property's recorded owner for consent; explicit
delegation is not modeled yet. The migration downgrade currently refuses when
audit rows exist, but should also refuse when publication or media-authorization
rows exist before it is approved for execution.

## Gate 1.7 implementation status

- `app/services/publication_policy.py` contains a storage/router-independent,
  fail-closed decision function. It is not registered with a route and does not
  create publication state.
- `PublicListingDTO` and `PublicMediaDTO` are explicit `extra="forbid"`
  allowlists using opaque `public_id`/`public_media_id`, sanitized copy and
  approximate coordinates only. They do not use ORM projection.
- `tests/test_publication_policy.py` covers complete evidence, missing consent,
  review/expiry/revocation, private media and DTO non-leakage.
- The model layer and a non-executed Alembic revision are now prepared:
  `app/models/publication.py` and
  `alembic/versions/1c7e9a2b4d60_publication_contract.py`. Existing `ACTIVE` rows
  remain non-public by default.
- `app/services/publication_lifecycle.py` provides internal lifecycle commands
  with scope, role and append-only audit checks. No router, public media URL or
  Keycloak change was made. Migration execution still requires explicit approval.

## Gate 1.9 review notes

- The migration FK order is `(property_id, id)` on both the unique key and the
  composite reference to `property_media`.
- Publication audit no longer cascades away with a publication and has a
  database append-only trigger in the prepared migration.
- Consent is owner-only until a delegated-consent model is approved.
- Review requires `ROLE_SUPERVISOR` or `ROLE_ADMIN`, existing consent, and a
  different subject from the consent actor.
- Media approval requires an existing consented publication and matching media
  ownership. No public URL is generated.
- Lifecycle publication rows use `FOR UPDATE`; callers must commit state and
  audit in one transaction.
