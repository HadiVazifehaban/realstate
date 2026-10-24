# SHEKARCHI Unified Login Cutover Runbook

**Project:** SHEKARCHI Keycloak Unified Login (Password + SMS OTP)
**Date:** 2026-10-20
**Target Image:** `shekarchi-keycloak:unified-final-26.0.8-20261020-r2`
**Backup Snapshot:** `20261020T102807Z`
**Rollback Image:** `shekarchi-keycloak:26.0.8` (sha256:2dcb6d4b1980)

---

## Pre-Flight Checklist

### 1. Backup Verification
- [ ] Confirm latest backup exists: `/home/app/.local/state/shekarchi-keycloak-backups/20261020T102807Z/`
- [ ] Verify database dump integrity:
  ```bash
  sha256sum /home/app/.local/state/shekarchi-keycloak-backups/keycloak-maskanchi-precutover-20261020T102807Z.dump
  # Expected: f5e659b146b74bcf99fa2fa2573b17365221536dc97a8ddf19497700428a422b
  ```
- [ ] Verify backup contains:
  - Browser flow configuration
  - Docker Compose files
  - Realm export
  - Theme archive
  - Environment snapshot

### 2. Secret Files Verification
- [ ] Verify all secret files exist and have mode 600:
  ```bash
  ls -la /home/app/.config/shekarchi/*.secret
  ```
- [ ] Files required:
  - `redis-password.secret`
  - `keycloak-otp-hmac.secret`
  - `captcha-hmac.secret`
  - `keycloak-redis-url.secret`
  - `backend-redis-url.secret`
  - `backend-otp-hmac.secret`
  - `mellipayamak.env`

### 3. Candidate Image Verification
- [ ] Verify candidate image exists:
  ```bash
  docker images shekarchi-keycloak:unified-final-26.0.8-20261020-r2
  # Expected ID: sha256:0d59e6f66d92
  ```
- [ ] Verify rollback image exists:
  ```bash
  docker images shekarchi-keycloak:26.0.8
  # Expected ID: sha256:2dcb6d4b1980
  ```

### 4. Network Verification
- [ ] Verify current network: `real_default`
- [ ] Verify `redis_internal` network will be created by overlay

### 5. Dependency Health Check
- [ ] PostgreSQL (avg_db): `docker ps | grep avg_db`
- [ ] Keycloak DB (avg_keycloak_db): `docker ps | grep avg_keycloak_db`
- [ ] Redis (avg_redis): `docker ps | grep avg_redis`
- [ ] Backend (avg_backend): `docker ps | grep avg_backend`

---

## Cutover Procedure

### Step 1: Compose Configuration Validation
**Command:**
```bash
cd /home/app/real
docker compose -f docker-compose.yml -f docker-compose.cutover.yml config > /tmp/cutover-merged.yml
```

**Prerequisites:** None
**Success Criteria:** No errors in output, merged configuration valid
**Duration:** 30 seconds
**Rollback:** N/A (read-only check)

**Failure Action:** Review error messages, fix overlay syntax

---

### Step 2: Stop Keycloak Container
**Command:**
```bash
docker compose stop keycloak
```

**Prerequisites:** Current Keycloak healthy
**Success Criteria:** Container stopped gracefully
**Duration:** 30-60 seconds
**Rollback:** `docker compose start keycloak`

**Failure Action:** Check logs, force stop if needed: `docker compose kill keycloak`

---

### Step 3: Redis Migration
**Command:**
```bash
# Backup current Redis data (optional but recommended)
docker exec avg_redis redis-cli SAVE
docker cp avg_redis:/data/dump.rdb /tmp/redis-backup-pre-cutover.rdb

# Apply cutover overlay
docker compose -f docker-compose.yml -f docker-compose.cutover.yml up -d redis
```

**Prerequisites:** Keycloak stopped
**Success Criteria:**
- Redis container running with authentication
- Port 6379 no longer published
- Healthcheck passing
**Duration:** 10-20 seconds
**Rollback:**
```bash
docker compose -f docker-compose.yml up -d redis
# Restore data if needed
docker cp /tmp/redis-backup-pre-cutover.rdb avg_redis:/data/dump.rdb
docker compose restart redis
```

**Failure Action:** Check Redis logs, verify secret file mount

---

### Step 4: Redis Health Verification
**Command:**
```bash
docker compose ps redis
docker exec avg_redis redis-cli -a "$(cat /home/app/.config/shekarchi/redis-password.secret)" ping
```

**Prerequisites:** Redis container running
**Success Criteria:** Returns `PONG`
**Duration:** 5 seconds
**Rollback:** Rollback Step 3

**Failure Action:** Check secret file content, container logs

---

### Step 5: Deploy Candidate Keycloak
**Command:**
```bash
docker compose -f docker-compose.yml -f docker-compose.cutover.yml up -d keycloak
```

**Prerequisites:** Redis healthy
**Success Criteria:** Container starts successfully
**Duration:** 60-90 seconds
**Rollback:**
```bash
docker compose -f docker-compose.yml stop keycloak
docker compose -f docker-compose.yml up -d keycloak
```

**Failure Action:** Check logs, verify secret mounts, image pull

---

### Step 6: Keycloak Health Verification
**Command:**
```bash
docker compose ps keycloak
curl -f http://localhost:8082/health/ready
curl -f http://localhost:8082/health/live
```

**Prerequisites:** Keycloak container running
**Success Criteria:** All health endpoints return 200
**Duration:** 60-120 seconds (startup time)
**Rollback:** Rollback Step 5

**Failure Action:** Check Keycloak logs, verify database connectivity, Redis connectivity

---

### Step 7: OIDC Discovery Verification
**Command:**
```bash
curl -s http://localhost:8082/realms/maskanchi/.well-known/openid-configuration | jq '.issuer'
```

**Prerequisites:** Keycloak healthy
**Success Criteria:** Returns `http://192.168.31.168:8082/realms/maskanchi`
**Duration:** 5 seconds
**Rollback:** Rollback Step 5

**Failure Action:** Check realm import, KC_HOSTNAME configuration

---

### Step 8: Browser Flow Preparation
**Command:**
```bash
# Verify current browser flow
curl -s -X GET "http://localhost:8082/admin/realms/maskanchi/authentication/flows/shekarchi-browser-passwordless" \
  -H "Authorization: Bearer \$TOKEN" | jq '.alias'
```

**Prerequisites:** Admin access token
**Success Criteria:** Flow exists and is configured
**Duration:** 10 seconds
**Rollback:** N/A (read-only check)

**Failure Action:** Restore flow from backup if needed

---

### Step 9: Browser Flow Activation
**Command:**
```bash
# Set browser flow (if not already set)
curl -s -X PUT "http://localhost:8082/admin/realms/maskanchi" \
  -H "Authorization: Bearer \$TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"browserFlow":"shekarchi-browser-passwordless"}'
```

**Prerequisites:** Admin access token, flow exists
**Success Criteria:** HTTP 204 No Content
**Duration:** 5 seconds
**Rollback:** Restore previous flow from backup

**Failure Action:** Verify flow exists, check admin permissions

---

### Step 10: Password Login Verification
**Manual Test:**
1. Open browser to `http://192.168.31.168:8082/realms/maskanchi/protocol/openid-connect/auth?client_id=shekarchi-frontend&redirect_uri=http://192.168.31.168:3000/dashboard/overview&response_type=code&scope=openid`
2. Select "Password" tab
3. Enter username: `admin`, password: `admin`
4. Complete CAPTCHA
5. Verify redirect to frontend with authorization code

**Prerequisites:** Browser flow active
**Success Criteria:** Successful login and redirect
**Duration:** 2 minutes
**Rollback:** Rollback Step 9

**Failure Action:** Check browser flow configuration, authenticator config

---

### Step 11: SMS OTP Verification (Mock Mode)
**Manual Test:**
1. Open browser to login page
2. Select "SMS" tab
3. Enter verified mobile: `09123456789` (or any from test users)
4. Complete CAPTCHA
5. Request OTP
6. Check logs for generated OTP (FakeSmsSenderService)
7. Enter OTP and verify login

**Prerequisites:** Password login working
**Success Criteria:** OTP generated in logs, login successful
**Duration:** 3 minutes
**Rollback:** Rollback Step 5

**Failure Action:** Check Redis connectivity, SMS provider configuration

---

### Step 12: Auth.js Session Verification
**Manual Test:**
1. After successful login, verify session in frontend
2. Check token contains expected claims
3. Verify refresh token functionality
4. Test logout

**Prerequisites:** Login successful
**Success Criteria:** Session management working
**Duration:** 5 minutes
**Rollback:** Rollback Step 5

**Failure Action:** Check OIDC client configuration, token settings

---

### Step 13: Backend API Verification
**Command:**
```bash
# Test protected endpoint with valid token
curl -H "Authorization: Bearer \$TOKEN" http://localhost:8080/api/v1/users/me
```

**Prerequisites:** Valid token from Step 12
**Success Criteria:** Returns user data
**Duration:** 10 seconds
**Rollback:** Rollback Step 5

**Failure Action:** Check backend configuration, Redis URL, OTP HMAC secret

---

### Step 14: Security Verification
**Checks:**
- [ ] Redis port 6379 not published
- [ ] Redis authentication required
- [ ] OTP HMAC secret not in environment (only from file)
- [ ] CAPTCHA HMAC secret not in environment (only from file)
- [ ] MelliPayamak config not in environment (only from file)
- [ ] SHEKARCHI_SMS_FAKE=false (for production)
- [ ] SHEKARCHI_ENV=production

**Prerequisites:** All services running
**Success Criteria:** All checks pass
**Duration:** 5 minutes
**Rollback:** Rollback Step 3 if Redis exposed

**Failure Action:** Fix secret mounts, environment variables

---

### Step 15: Monitoring Setup
**Actions:**
- [ ] Enable Keycloak events if needed
- [ ] Configure log aggregation
- [ ] Set up alerts for:
  - Redis connection failures
  - OTP delivery failures
  - Authentication failures
  - High error rates

**Prerequisites:** Security verification passed
**Success Criteria:** Monitoring active
**Duration:** 15 minutes
**Rollback:** N/A

**Failure Action:** Continue without monitoring, add later

---

## Rollback Triggers

Execute rollback if ANY of the following occur:

1. **Critical:**
   - Keycloak fails to start after 5 minutes
   - Database connection errors
   - Redis authentication failures
   - Complete login failure for all users
   - Data corruption detected

2. **Major:**
   - SMS OTP not working (if critical to operations)
   - Password login not working
   - Session management broken
   - Secret exposure detected

3. **Minor:**
   - UI issues (can be fixed post-cutover)
   - Performance degradation (monitor first)
   - Non-critical authentication errors

---

## Rollback Procedure

### Immediate Rollback (Critical)
```bash
cd /home/app/real

# Stop cutover services
docker compose -f docker-compose.yml -f docker-compose.cutover.yml stop keycloak redis

# Restore original configuration
docker compose -f docker-compose.yml up -d redis
docker compose -f docker-compose.yml up -d keycloak

# Verify services
docker compose ps
curl -f http://localhost:8082/health/ready
```

### Full Rollback (Database Issues)
```bash
cd /home/app/real

# Stop all services
docker compose stop keycloak keycloak-db

# Restore database from backup
docker run --rm -v real_avg_keycloakpgdata:/data -v /home/app/.local/state/shekarchi-keycloak-backups:/backup \
  postgres:16-alpine sh -c "
  rm -rf /data/*
  tar xzf /backup/keycloak-maskanchi-precutover-20261020T102807Z.dump -C /data
"

# Start services
docker compose start keycloak-db
# Wait for DB healthy
docker compose start keycloak
```

### Flow Configuration Rollback
```bash
# Restore browser flow from backup
curl -s -X PUT "http://localhost:8082/admin/realms/maskanchi" \
  -H "Authorization: Bearer \$TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"browserFlow":"browser"}'
```

---

## Post-Cutover Verification

### 1. Smoke Tests
- [ ] Admin login (password)
- [ ] Agent login (password)
- [ ] Junior broker login (SMS OTP)
- [ ] Token refresh
- [ ] Logout
- [ ] Backend API access

### 2. Load Testing (Optional)
- [ ] Concurrent login attempts
- [ ] OTP rate limiting
- [ ] CAPTCHA rate limiting
- [ ] Session concurrency

### 3. Security Review
- [ ] Verify no secrets in logs
- [ ] Verify Redis not accessible externally
- [ ] Verify TLS if enabled (future)
- [ ] Verify audit logs

---

## Timeline Estimate

| Step | Duration | Notes |
|------|----------|-------|
| Pre-flight | 10 min | Includes backup verification |
| Stop Keycloak | 1 min | Graceful shutdown |
| Redis Migration | 1 min | Quick restart |
| Deploy Keycloak | 2 min | Image pull time |
| Health Checks | 3 min | Startup wait |
| Verification | 10 min | Manual tests |
| **Total Downtime** | **5-8 min | During Steps 2-5 |
| **Total Cutover** | **30 min | Including verification |

---

## Emergency Contacts

- **System Administrator:** [TBD]
- **Database Administrator:** [TBD]
- **Network Administrator:** [TBD]
- **Application Owner:** [TBD]

---

## Notes

- All commands assume execution from `/home/app/real`
- Rollback image `shekarchi-keycloak:26.0.8` must remain available
- Do not delete backup files until cutover is confirmed stable (minimum 24 hours)
- Monitor error logs for first 24 hours post-cutover
- Keep MelliPayamak in disabled state until credentials are verified and approved
- Brute Force Protection requires policy approval before enabling
