# Realm Configuration Guide

## Required Authentication Flows

### 1. shekarchi-browser-passwordless (Browser Flow)
Executions:
1. Cookie (optional)
2. Shekarchi SMS Authenticator (FLOW TYPE = PASSWORDLESS) - REQUIRED

### 2. shekarchi-browser-mfa (Sub-Flow/Browser Flow)
After Username Password Form success:
1. Username Password Form (REQUIRED)
2. Shekarchi SMS Authenticator (FLOW TYPE = MFA) - REQUIRED

### 3. Login Method Selection
Implement explicit selection form (login-method-select.ftl). Do NOT rely solely on ALTERNATIVE executions.
