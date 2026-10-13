# syntax=docker/dockerfile:1@sha256:4edf897a3ffa55b89f906fc8cc78afdb3f1834cc9c7083565e611a8a7d5fe99e
FROM python:3.12.15-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258 AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1 PYTHONIOENCODING=utf-8
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

FROM base AS dependencies
WORKDIR /build
COPY requirements.lock ./
RUN python -m venv /opt/venv
RUN --mount=type=cache,target=/root/.cache/pip \
    /opt/venv/bin/python -m pip install --prefer-binary -r requirements.lock
# Build tooling belongs to the builder, not the transferred runtime environment.
RUN python -m pip install --no-cache-dir hatchling==1.27.0
COPY pyproject.toml ./project/
COPY src ./project/src
WORKDIR /build/project
RUN python -m hatchling build -t wheel \
    && /opt/venv/bin/python -m pip install --no-deps dist/*.whl \
    && /opt/venv/bin/python -m pip check

FROM base AS runtime
ENV PATH=/opt/venv/bin:$PATH \
    HF_HOME=/models/huggingface HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
    REGULARAG_RAG_CONFIG_PATH=configs/rag/final.json \
    REGULARAG_PIPELINE_TRACING_ENABLED=true REGULARAG_LOG_LEVEL=INFO
RUN groupadd --gid 10001 regularag && useradd --uid 10001 --gid 10001 --create-home regularag \
    && mkdir -p /app/data/raw /app/data/processed /models/huggingface \
    && chown -R regularag:regularag /models /app/data
COPY --from=dependencies /opt/venv /opt/venv
WORKDIR /app
COPY configs ./configs
COPY scripts ./scripts
COPY data/manifests ./data/manifests
# Preserve inspectable source bytes for provenance tools; imports use the installed wheel.
COPY src ./src
COPY requirements.lock pyproject.toml ./
USER regularag
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=6s --start-period=15s --retries=5 \
    CMD ["python", "scripts/docker_healthcheck.py"]
CMD ["python", "-m", "uvicorn", "regularag.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
