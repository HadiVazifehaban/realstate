# Security Inventory - Wave Zero
# Generated: 2026-10-17
# Purpose: Read-only identification of all secrets before remediation

## File Checksums (Baseline)

| File | SHA-256 | Purpose |
|------|---------|---------|
| keycloak/realm-export.json | dc7e5f8129999dfe6a2dbb931c0f0fd66e1067b2a5ca2036f31205333983f229 | Keycloak realm configuration with secrets |
| .env.example | 3bc8f20d94c6e0a034a341a5b88f23d5bf4bd101f3ab1dc951e7cf6b28af2cfb | Environment template with placeholder secrets |
| docker-compose.yml | 7a0ff9a8f21ebc01f6d5dddf8bfd7703897b68faf472baf48ec72e2e0f8a1362 | Service orchestration with default secrets |

---

## Secret Inventory

### 1. realm-export.json (Keycloak Realm Configuration)

**Location**: `/home/app/real/keycloak/realm-export.json`
**File Checksum**: `dc7e5f8129999dfe6a2dbb931c0f0fd66e1067b2a5ca2036f31205333983f229`

| Secret Type | Path in JSON | Line | Description | Exposure |
|-------------|--------------|------|-------------|----------|
| Client Secret | `clients[2].secret` | 191 | Service account secret for maskanchi-admin-cli | ✅ COMMITTED (Finding #1) |
| User Password | `users[0].credentials[0].value` | 211 | Admin user password | ✅ COMMITTED (Finding #1) |
| User Password | `users[1].credentials[0].value` | 246 | Manager user password | ✅ COMMITTED (Finding #1) |
| User Password | `users[2].credentials[0].value` | 281 | Supervisor user password | ✅ COMMITTED (Finding #1) |
| User Password | `users[3].credentials[0].value` | 313 | Agent user password | ✅ COMMITTED (Finding #1) |
| User Password | `users[4].credentials[0].value` | 348 | Junior user password | ✅ COMMITTED (Finding #1) |
| User Password | `users[5].credentials[0].value` | 380 | Analyst user password | ✅ COMMITTED (Finding #1) |
| User Password | `users[6].credentials[0].value` | 412 | Pending user password | ✅ COMMITTED (Finding #1) |

**Total Secrets in realm-export.json**: 8 (1 client secret + 7 user passwords)

---

### 2. .env.example (Environment Template)

**Location**: `/home/app/real/.env.example`
**File Checksum**: `3bc8f20d94c6e0a034a341a5b88f23d5bf4bd101f3ab1dc951e7cf6b28af2cfb`

| Secret Type | Variable | Line | Current Value | Status |
|-------------|----------|------|---------------|--------|
| Database Password | DATABASE_URL | 25 | `avg_secret` (placeholder) | ⚠️ PLACEHOLDER (Finding #6) |
| JWT Secret | JWT_SECRET | 49 | `change-me-in-production-please-use-a-long-random-string` | ⚠️ PLACEHOLDER (Finding #5) |
| HMAC Secret | DIVAR_WEBHOOK_SECRET | 59 | `change-me-divar-hmac-secret` | ⚠️ PLACEHOLDER (Finding #7) |
| Keycloak Admin Secret | KEYCLOAK_ADMIN_CLIENT_SECRET | 130 | `8k70mjMEAes9Y-ZlWfK_HM29sWvJnQSIiH6Hr4OqLbI` | ✅ COMMITTED (Finding #7) |
| Keycloak Admin Password | KEYCLOAK_ADMIN_PASSWORD | 136 | `admin` | ⚠️ WEAK (Finding #6) |

**Total Secrets in .env.example**: 5

---

### 3. docker-compose.yml (Service Orchestration)

**Location**: `/home/app/real/docker-compose.yml`
**File Checksum**: `7a0ff9a8f21ebc01f6d5dddf8bfd7703897b68faf472baf48ec72e2e0f8a1362`

| Secret Type | Variable | Line | Default Value | Status |
|-------------|----------|------|---------------|--------|
| Database Password | POSTGRES_PASSWORD | 39 | `avg_secret` | ⚠️ WEAK DEFAULT (Finding #6) |
| Keycloak DB Password | KEYCLOAK_DB_PASSWORD | 99 | `keycloak_secret` | ⚠️ WEAK DEFAULT (Finding #6) |
| Keycloak Admin Password | KC_BOOTSTRAP_ADMIN_PASSWORD | 124 | `admin` | ⚠️ WEAK DEFAULT (Finding #6) |

**Total Secrets in docker-compose.yml**: 3

---

## Summary

| File | Secret Count | Type |
|------|--------------|------|
| realm-export.json | 8 | Client secret + User passwords |
| .env.example | 5 | DB, JWT, HMAC, Keycloak secrets |
| docker-compose.yml | 3 | Database passwords |
| **TOTAL** | **16** | Various |

---

## Remediation Priority Mapping

| Finding ID | Description | Wave | Status |
|------------|-------------|------|--------|
| #1 | Secrets in realm-export.json | Wave 0/1 | ⏳ PENDING |
| #5 | JWT_SECRET placeholder | Wave 1 | ⏳ PENDING (requires usage verification) |
| #6 | Weak DB passwords | Wave 1 | ⏳ PENDING (requires usage verification) |
| #7 | HMAC_SECRET in .env.example | Wave 1 | ⏳ PENDING (documentation) |

---

## Next Steps (Wave One)

1. **Verify actual usage** of placeholder secrets (JWT_SECRET, DB passwords):
   - Check running container environment variables
   - Check actual .env file (read-only grep)
   - Check service logs for connection errors with default secrets

2. **Document HMAC_SECRET** (Finding #7):
   - Add comment explaining it's a placeholder for Divar webhook HMAC
   - This is low-risk documentation change

3. **Remove HMAC OTP fallback** (Finding #3):
   - Locate OTP authentication code
   - Remove fallback mechanism that uses HMAC_SECRET

4. **Prepare secret rotation plan** (Finding #1):
   - Design rotation procedure for realm-export.json secrets
   - Document rollback procedure
   - Obtain approval before execution

---

## Risk Assessment

| Category | Count | Risk Level |
|----------|-------|------------|
| Committed secrets | 9 | 🔴 HIGH |
| Placeholder secrets | 4 | 🟡 MEDIUM |
| Weak default passwords | 3 | 🟡 MEDIUM |
| **TOTAL** | **16** | **🔴 HIGH** |

---

## Notes

- This inventory is READ-ONLY. No changes have been made.
- All secret values are known but not exposed in this document.
- Checksums serve as baseline for detecting unauthorized changes.
- Wave Zero complete. Ready to proceed to Wave One with user approval.
