# Network reports Phase 1A — tenant isolation

## Scope and explicit access policy

Only `GET /api/v1/network/overview` and `GET /api/v1/network/reports`, their
frontend callers, and the unsafe monetary presentation are changed. Response
fields and legacy financial formulas are retained. No operational data or
database migrations are changed.

The signed Principal is authoritative. `ROLE_AGENCY_MANAGER`, `ROLE_ADMIN`, and
`ROLE_SUPERVISOR` may read aggregates only for their own non-zero UUID tenant.
An administrator or supervisor is not granted global financial visibility.
Missing, malformed or zero tenant is denied (403), even with an agency query.

No independent global network-report permission exists in the examined policy.
Billing `financial_admin` is not a network-report grant. No new permission is
introduced. A network administrator without a tenant remains denied.

**Blocked pending policy:** Personal broker reports cannot safely be derived
from the mixed username, agency and unassigned ownership fields. Senior brokers
receive 403 `agency_reports_required`; junior brokers remain denied by the
existing route policy. No agency-wide substitute is exposed. Personal reports
and cross-tenant network management reports require a separate explicit policy
and reliable attribution before implementation. This is an intentional access
restriction, not a claim that personal analytics has been implemented.

## Query isolation

- Every operational aggregate requires the tenant on one of the record's two
  agency sides; omitting the query parameter never removes this condition.
- Agreement sums/status counts require source or target tenant participation.
- Payment sums join Payment -> Allocation -> Agreement, require allocation
  `agency_id == tenant`, and also require agreement participation. Another
  beneficiary's payments, unassigned beneficiaries, orphan records and a
  tenant allocation on an unrelated agreement are excluded. Inner joins by
  unique IDs do not multiply payments.
- Audit aggregates require actor or target agency equal to tenant. Null/null
  historical events are excluded, not guessed from usernames or details.
- Agency counts describe only the signed tenant, not the global directory.

## Parameter compatibility

Canonical query: `agency_id`. Existing TypeScript callers may keep passing
`agencyId` to the client function; it serializes `agency_id` on the wire.
The server continues accepting the legacy `agencyId` query, deprecated in
OpenAPI. Both aliases must agree if provided (422 otherwise). Any valid but
foreign requested scope is rejected (403); malformed UUID inputs return 422.

## Financial limits (not fixed in this phase)

`total_basis`, `total_paid`, `total_remaining` and overview counterparts remain
legacy numeric API fields. `total_remaining = max(total_basis-total_paid, 0)` is
unchanged and is **not verified receivables**. Agreement basis is not agency
revenue. Currency grouping, historical IRR/Toman ambiguity, Decimal-safe DTOs,
receipt verification, costs, due dates and accounting attribution are unresolved.

Reports no longer display these uncertain monetary values as financial KPIs;
the overview no longer formats agreement basis as Toman. Counts remain visible.
Other API consumers must not treat the retained numeric fields as audited
financial reports. Current-state conversion remains non-cohort-based.

## Verification and operational boundaries

`tests/test_network_reports_access.py` exercises HTTP authentication/authorization
and actual SQL aggregates against synthetic in-memory SQLite, including the
real application router. License is overridden for report isolation tests;
separate license regression tests exercise the existing admin exemption.
Client tests cover canonical serialization; report-view tests cover unsafe
money suppression and hiding cached results on errors.

No production database queries, migrations, Keycloak changes, restart or deploy.
SQLite tests do not establish PostgreSQL performance, live token/realm policy,
or historical data quality. Related commission/dispute/audit CRUD authorization
is not changed by this report-only patch and requires its own approved scope.

### Recorded isolated checks

- Backend: 110 passed across report isolation, share authorization, admin license,
  Keycloak identity and token-flow suites. Report isolation accounts for 64 cases.
- Frontend: 13 passed across report-client, report-view and shared network tests.
- TypeScript: `tsc --noEmit --incremental false` exit 0.
- Frontend targeted oxlint: zero warnings/errors. Python AST parse and
  `git diff --check` passed. Ruff is not installed in the repository virtualenv.
- No build, browser E2E, production request or deployment was performed in this
  phase. Mocked Principal/token verification and isolated SQL test behavior are
  not a live Keycloak integration test.

Overall requested Phase 1A remains **PARTIALLY COMPLETE / policy-blocked**:
the existing aggregate endpoints are hardened and tested, but personal broker
reports and independently authorized network-wide access are intentionally not
implemented without a business/authorization decision. Do not label the entire
requested phase COMPLETE merely because the isolation tests pass.

Rollback is source-level only; no data rollback is required. Reverting isolation
reopens the original disclosure, so disable access rather than restoring unsafe
global queries if operational rollback becomes necessary.