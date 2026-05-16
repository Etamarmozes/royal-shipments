# syntax=docker/dockerfile:1.7
# ------------------------------------------------------------------------
# Royal Linen Shipments — production frontend image
# ------------------------------------------------------------------------
# Multi-stage:
#   1. `builder`  Node 20 -> tsc + vite build -> /app/dist
#   2. `runtime`  nginx:alpine serves the static SPA on port 80,
#                 and reverse-proxies /api/* to the backend container.
# Final image: ~50 MB.
# ------------------------------------------------------------------------

ARG NODE_VERSION=20

# ============================ stage 1: builder ============================
FROM node:${NODE_VERSION}-alpine AS builder

WORKDIR /app

# Lockfile-first to maximise layer caching — `npm ci` is reproducible.
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund

# Now the source.  Any code change invalidates only this and the next layer.
COPY . .

# Production build (tsc type-check + vite build → /app/dist).
# VITE_API_BASE defaults to /api so the in-container nginx can proxy.
ARG VITE_API_BASE=/api
ENV VITE_API_BASE=${VITE_API_BASE}
RUN npm run build


# ============================ stage 2: runtime ============================
FROM nginx:1.27-alpine AS runtime

# Strip the upstream default site + drop in our SPA config.
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/royal-linen.conf

# Copy the built SPA.
COPY --from=builder /app/dist /usr/share/nginx/html

# nginx:alpine already includes wget — used for the healthcheck below.
EXPOSE 80

HEALTHCHECK --interval=20s --timeout=4s --start-period=10s --retries=5 \
    CMD wget --quiet --tries=1 --spider http://127.0.0.1:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
