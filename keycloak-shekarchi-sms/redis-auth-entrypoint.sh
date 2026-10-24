#!/bin/sh
set -eu

# Runs as root only long enough to materialize a private Redis config in the
# container's writable layer. The upstream Redis entrypoint then drops to UID 999.
secret_file=${REDIS_PASSWORD_FILE:-/run/secrets/redis_password}
if [ ! -r "$secret_file" ]; then
  echo 'Redis password secret is unavailable' >&2
  exit 1
fi
password=$(cat "$secret_file")
if [ -z "$password" ]; then
  echo 'Redis password secret is empty' >&2
  exit 1
fi
case "$password" in
  *[!A-Za-z0-9_-]*) echo 'Redis password has unsupported characters' >&2; exit 1 ;;
esac

umask 077
config=/tmp/redis-auth-runtime.conf
cat > "$config" <<EOF
bind 0.0.0.0
protected-mode yes
requirepass $password
save 3600 1
save 300 100
save 60 10000
appendonly no
EOF
chown redis:redis "$config"
chmod 600 "$config"
unset password
exec /usr/local/bin/docker-entrypoint.sh redis-server "$config"
