# Dockerfile — AutoFix AI
# Multi-stage build. Non-root user. Minimal attack surface.

# ── Stage 1: builder ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# System deps for argon2-cffi, asyncpg
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Non-root user — never run as root in production
RUN groupadd --gid 1001 autofix && \
    useradd --uid 1001 --gid autofix --shell /bin/bash --create-home autofix

WORKDIR /app

# Runtime system deps only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

COPY --chown=autofix:autofix . .

# Wiki dir writeable by app user
RUN mkdir -p debug_wiki/errors && chown -R autofix:autofix debug_wiki

USER autofix

EXPOSE 8000

# Healthcheck for Docker Compose / K8s
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
<<<<<<< HEAD
     "--workers", "1", "--log-level", "info"]
=======
     "--workers", "1", "--log-level", "info", "--no-access-log"]
>>>>>>> origin/main
