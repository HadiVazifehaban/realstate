/**
 * Which class of party the node will record this listing under.
 *
 * Mirrors ``app.core.identity.submitter_type_for`` for *display only*: the
 * server re-derives it from the signed token and is the enforcement point, so
 * this file cannot grant anything. It exists so the person filling the form is
 * told up front that the row will read «شخص حقیقی» or «بنگاه», instead of
 * discovering it on the listing card afterwards.
 *
 * The least-privileged submitter role wins, matching the backend: a token
 * holding both ROLE_OWNER and ROLE_SENIOR_BROKER belongs to somebody who both
 * owns property and works a desk, and folding that to AGENCY would silently
 * reclassify their own listing as office business.
 *
 * Returns null when the caller holds no submitter role -- the API will refuse
 * the write with 403, and the form says so rather than promising a badge.
 */

import type { SubmitterType } from '../types';

/** Realm role -> the submitter class it implies. Keep in step with the backend. */
const SUBMITTER_BY_REALM_ROLE: Record<string, SubmitterType> = {
  ROLE_OWNER: 'PERSON',
  ROLE_SENIOR_BROKER: 'AGENCY',
  ROLE_JUNIOR_BROKER: 'AGENCY',
  ROLE_AGENCY_MANAGER: 'AGENCY',
  ROLE_SUPERVISOR: 'AGENCY',
  ROLE_ADMIN: 'AGENCY'
};

/** Lower wins, matching ``ROLE_ORDER`` in ``app/core/identity.py``. */
const ROLE_RANK: Record<string, number> = {
  ROLE_OWNER: 2,
  ROLE_SENIOR_BROKER: 3,
  ROLE_JUNIOR_BROKER: 3,
  ROLE_AGENCY_MANAGER: 4,
  ROLE_SUPERVISOR: 5,
  ROLE_ADMIN: 6
};

export function submitterKindFromRoles(
  roles: readonly string[]
): SubmitterType | null {
  const matched = roles.filter(
    (role) => role in SUBMITTER_BY_REALM_ROLE && !role.startsWith('default-')
  );
  if (matched.length === 0) return null;
  const least = matched.reduce((best, role) =>
    ROLE_RANK[role] < ROLE_RANK[best] ? role : best
  );
  return SUBMITTER_BY_REALM_ROLE[least];
}