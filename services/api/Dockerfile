FROM ghcr.io/astral-sh/uv:0.11.8 AS uv

FROM python:3.12.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends libpango-1.0-0 libpangoft2-1.0-0 fonts-noto-core \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/baseera-venv \
    PATH="/opt/baseera-venv/bin:$PATH" \
    PYTHONPATH=/app/services/api

RUN groupadd --system --gid 10001 baseera \
    && useradd --system --uid 10001 --gid baseera --home-dir /nonexistent baseera \
    && mkdir -p /app /data/artifacts \
    && chown -R baseera:baseera /app /data

COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --extra advanced --no-install-project \
    && rm -rf /root/.cache/uv

COPY --chown=baseera:baseera services/api ./services/api
USER baseera
EXPOSE 8000

CMD ["uvicorn", "baseera.main:app", "--host", "0.0.0.0", "--port", "8000"]
