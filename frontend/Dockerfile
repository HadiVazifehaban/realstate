ARG NODE_VERSION=22-slim

# ---------------------------------------------------------------------------
# Stage 1 — dependencies
#
# The old Dockerfile ran `bun install --no-save` against bun.lock, a lock that
# predates next-auth, so the shipped image silently contained ~21 packages and
# no Auth.js -> every API call 401'd with `missing_token`. `npm ci` installs
# strictly from package-lock.json (which does declare next-auth@5 beta).
# ---------------------------------------------------------------------------
FROM node:${NODE_VERSION} AS dependencies

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --legacy-peer-deps

# ---------------------------------------------------------------------------
# Stage 2 — builder
# ---------------------------------------------------------------------------
FROM node:${NODE_VERSION} AS builder

WORKDIR /app

ARG NEXT_PUBLIC_KEYCLOAK_ISSUER
ENV NEXT_PUBLIC_KEYCLOAK_ISSUER=${NEXT_PUBLIC_KEYCLOAK_ISSUER}
# Public like the issuer: the browser loads tiles straight from the tile server,
# so a baked-in localhost would resolve to the phone instead of the office node.
ARG NEXT_PUBLIC_TILE_URL
ENV NEXT_PUBLIC_TILE_URL=${NEXT_PUBLIC_TILE_URL}
ENV BUILD_STANDALONE=true

COPY --from=dependencies /app/node_modules ./node_modules
COPY . .

RUN npm run build

# ---------------------------------------------------------------------------
# Stage 3 — runner (slim, no dev deps, non-root)
# ---------------------------------------------------------------------------
FROM node:${NODE_VERSION} AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

COPY --from=builder --chown=node:node /app/public ./public
COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static

USER node
EXPOSE 3000

CMD ["node", "server.js"]
