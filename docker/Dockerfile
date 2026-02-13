FROM python:3.13-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry poetry-plugin-export

# Copy manifests first for layer caching
COPY pyproject.toml poetry.lock ./

# Install deps into isolated venv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN poetry export --without dev --format requirements.txt --output requirements.txt \
    && pip install --no-cache-dir -r requirements.txt

# Install the package itself (source + entry point)
COPY README.md ./
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini ./
RUN pip install --no-cache-dir --no-deps .

# ---- runtime ----
FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Include alembic for optional in-container migrations
COPY --from=builder /build/alembic/ alembic/
COPY --from=builder /build/alembic.ini ./

EXPOSE 8000 8001 8002

CMD ["codex-graph", "serve"]
