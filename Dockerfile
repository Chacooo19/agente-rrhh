# syntax=docker/dockerfile:1
# Imagen ligera: python slim + FastEmbed (ONNX, sin PyTorch). El índice RAG y el modelo de
# embeddings se generan en el build para que el contenedor arranque listo y sin red extra.

FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    FASTEMBED_CACHE_PATH=/app/models_cache
WORKDIR /app

FROM base AS deps
COPY pyproject.toml ./
# Solo dependencias de ejecución, leídas de pyproject.toml (única fuente de verdad)
RUN python -c "import tomllib; print('\\n'.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))" > requirements.txt \
    && pip install --prefix=/install -r requirements.txt

FROM base AS runtime
COPY --from=deps /install /usr/local
COPY app ./app
COPY prompts ./prompts
COPY data ./data
COPY scripts ./scripts
COPY evals ./evals
# Descarga el modelo de embeddings y construye el índice vectorial (LFT + documentos internos)
RUN python -m app.rag.ingest

RUN useradd --create-home --uid 1000 agente \
    && mkdir -p /app/var \
    && chown -R agente:agente /app/var /app/models_cache
USER agente

ENV DB_PATH=/app/var/rrhh.db
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/salud', timeout=4)"
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
