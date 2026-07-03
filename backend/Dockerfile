# =============================================================================
# purpose:  Multi-stage build for the LMS FastAPI application.
#           Used by both lms-api and lms-migrate containers in docker-compose.
#           The command override in docker-compose.yml determines behaviour:
#             lms-api:     uvicorn app.main:app ...
#             lms-migrate: alembic upgrade head
# implements: LMS-SDD-002 §5.1 (Docker Compose, single-node deployment)
#             LMS-SDD-002 §4   (FastAPI, Uvicorn, SQLAlchemy, redis-py)
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Builder — install dependencies into a virtual environment.
# Separating this stage keeps the final image lean.
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /build

# Install system dependencies needed to compile Python packages.
# aiomysql and cryptography (for python-jose RS256) may need build tools.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for Docker layer caching.
COPY requirements.txt .

# Install into a venv for clean separation.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------------------
# Stage 2: Runtime — minimal image with only the venv and application code.
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

# Non-root user for security.
RUN groupadd -r lms && useradd -r -g lms lms

WORKDIR /app

# Runtime system dependencies only (no build tools).
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder stage.
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code.
COPY --chown=lms:lms . .

# Python runtime settings.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

USER lms

EXPOSE 8000

# Default command — overridden by docker-compose.yml for lms-migrate.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
