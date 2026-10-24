# Troubleshooting

## Provider not discovered
- Ensure JAR is in providers/
- Run kc.sh build after adding
- Check META-INF/services files present
- Verify Keycloak version matches 26.0

## Authenticator discovered but no SMS login page appears
- The SPI being loaded (kc.sh build log shows `shekarchi-sms-authenticator`) is NOT enough:
  the authenticator must also be added as an REQUIRED execution to a browser flow.
- Create/assign the flows described in REALM_CONFIG.md (shekarchi-browser-passwordless,
  shekarchi-browser-mfa) and bind them as the realm browser flow (realm-admin console:
  Authentication → Flows → Bind flow).
- Verify binding in DB:
  SELECT af.alias, ae.authenticator FROM authentication_execution ae
  JOIN authentication_flow af ON ae.flow_id=af.id
  JOIN realm r ON af.realm_id=r.id
  WHERE r.name='maskanchi' AND ae.authenticator LIKE '%shekarchi%';
- Empty result = flow not bound yet; the login page will keep showing the stock password form.
