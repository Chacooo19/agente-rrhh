# ADR-0006: Docker multi-etapa con índice precalculado y Docker Compose

- **Estado:** aceptado
- **Fecha:** 2026-11-24

## Contexto

El proyecto debe arrancar "a la primera" con un solo comando en la máquina del evaluador,
con imágenes ligeras y variables de entorno bien manejadas. El paso más lento y frágil es
descargar el modelo de embeddings y construir el índice.

## Opciones consideradas

1. Construir el índice **al arrancar** el contenedor: imagen pequeña, pero el primer
   arranque tarda y depende de la red en tiempo de ejecución.
2. **Construir el índice en el `docker build`**: build más largo, arranque inmediato.
3. Incluir un contenedor de Ollama en el Compose para el modelo de lenguaje.

## Decisión

- **Dockerfile multi-etapa** sobre `python:3.12-slim`: una etapa instala solo las
  dependencias de ejecución (leídas de `pyproject.toml`), la final copia código y datos,
  descarga el modelo de embeddings y **construye el índice** (`python -m app.rag.ingest`).
  Corre como usuario sin privilegios y tiene `HEALTHCHECK` sobre `/api/salud`.
- **Compose** con un servicio, volumen para la base SQLite (usuarios y tickets persisten) y
  `env_file` opcional: sin `.env` la app arranca y la interfaz explica que falta la API key.
- **No** se incluye Ollama en el Compose: una descarga de ~14 GB no es "a la primera". Quien
  quiera el modo local apunta `OLLAMA_API_BASE` al Ollama de su máquina
  (`host.docker.internal`, ya mapeado en el Compose).

## Consecuencias

- ✅ `docker compose up --build` y listo; los secretos solo viven en `.env` (ignorado por git
  y por `.dockerignore`).
- ✅ Sin PyTorch, la imagen queda en cientos de MB en lugar de varios GB.
- ⚠️ El build necesita red para PyPI y Hugging Face (descarga del modelo de embeddings).
- ⚠️ Cambiar un documento implica reconstruir la imagen; con más tiempo, la ingesta sería un
  job separado que escribe el índice en un volumen compartido.
