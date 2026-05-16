# syntax=docker/dockerfile:1.7
# ------------------------------------------------------------------------
# Royal Linen Shipments — production backend image
# ------------------------------------------------------------------------
# Multi-stage build:
#   1. `builder`  installs build tools + builds Python wheels into a venv
#   2. `runtime`  is a minimal slim image with just the venv + app code,
#                 running as a non-root user.
# Final image: ~180 MB.
# ------------------------------------------------------------------------

ARG PYTHON_VERSION=3.12

# ============================ stage 1: builder ============================
FROM python:${PYTHON_VERSION}-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build-time deps.  libpq-dev is needed even though we ship psycopg2-binary
# in case it ever falls back to a source build for the running arch.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Create an isolated venv so we can copy it verbatim into the runtime image.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python deps first (cached layer — only re-runs when requirements change)
COPY requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip \
 && pip install -r /tmp/requirements.txt


# ============================ stage 2: runtime ============================
FROM python:${PYTHON_VERSION}-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    UPLOADS_DIR=/app/uploads \
    FILE_STORAGE_PATH=/app/uploads \
    TZ=Asia/Jerusalem

# Runtime libs only — no compilers in the final image.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
        tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 1001 royal \
    && useradd  --system --uid 1001 --gid royal --create-home --shell /bin/bash royal

WORKDIR /app

# Bring in the prebuilt venv from the builder stage.
COPY --from=builder /opt/venv /opt/venv

# Copy app code (owned by the non-root user).
COPY --chown=royal:royal app    /app/app
COPY --chown=royal:royal scripts /app/scripts

# Persistent upload + data dirs (volumes are mounted over these at runtime).
RUN mkdir -p /app/uploads /app/data /app/logs \
 && chown -R royal:royal /app/uploads /app/data /app/logs

USER royal

# 8000 is what uvicorn binds inside the container; the host-side nginx
# reverse-proxies api.royallinenshipments.com → http://backend:8000.
EXPOSE 8000

# Container-level health probe.  Docker / compose use this to decide
# when the service is "ready" (used by depends_on conditions).
HEALTHCHECK --interval=20s --timeout=5s --start-period=20s --retries=5 \
    CMD curl --fail --silent --max-time 4 http://127.0.0.1:8000/health || exit 1

# `--workers 2` is a sensible default for a small Hetzner box; tune via
# the BACKEND_WORKERS env var if you have more CPUs.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${BACKEND_WORKERS:-2} --proxy-headers --forwarded-allow-ips=*"]
