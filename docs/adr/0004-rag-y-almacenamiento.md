# ADR-0004: RAG con chunking por artículo, embeddings locales, índice NumPy y SQLite

- **Estado:** aceptado
- **Fecha:** 2026-11-24

## Contexto

Corpus: la LFT completa (~1,000 artículos, PDF) y dos documentos internos en Markdown.
Las respuestas deben citar artículo exacto. Datos estructurados: 24 empleados, usuarios y
tickets. Todo debe levantarse con `docker compose up` sin servicios adicionales.

## Opciones consideradas

**Chunking**
1. Ventanas fijas de N tokens con traslape.
2. **Por artículo** (unidad jurídica), subdividiendo artículos largos.

**Embeddings**
1. API de embeddings (OpenAI, Gemini): calidad alta, costo y dependencia de red.
2. `sentence-transformers` con PyTorch: local pero imagen de >2 GB.
3. **FastEmbed (ONNX) con `paraphrase-multilingual-MiniLM-L12-v2`**: local, multilingüe,
   ~220 MB, sin PyTorch.

**Almacén vectorial**
1. Qdrant / Chroma / pgvector como servicio.
2. **Matriz NumPy + JSON en disco** con búsqueda exacta.

**Datos estructurados**
1. Postgres. 2. **SQLite.**

## Decisión

- **Chunking por artículo** con regex sobre el texto del PDF (quitando encabezados y pies de
  página de la Cámara de Diputados). Artículos de más de 1,500 caracteres se parten en
  ventanas con 200 de traslape, conservando el número de artículo. Cada fragmento lleva
  `id` estable (`lft-art76`, `reglamento-interno-art7`) para citar y evaluar.
- Al vectorizar se antepone `fuente + título` al texto, para que "aguinaldo de la empresa"
  encuentre el artículo del reglamento aunque el cuerpo no repita esas palabras.
- **Búsqueda:** coseno exacto, top-k=3 (cada fragmento recortado a 900 caracteres al enviarse al modelo), **umbral mínimo** (`RAG_MIN_SCORE`, 0.35): por debajo
  la tool responde `encontrado=false` y el agente dice que no sabe (RF-05). Si la pregunta
  menciona "artículo N", ese fragmento recibe un bono en el ranking.
- **Seguridad en la ingesta:** se quitan comentarios HTML y se marcan fragmentos con
  instrucciones para la IA (ver `docs/arquitectura.md`).
- **NumPy** para ~1,100 vectores de 384 dimensiones: la búsqueda tarda milisegundos y no hay
  que operar otro contenedor. El índice se construye en el `docker build`.
- **SQLite** para empleados, usuarios y tickets: un archivo en un volumen de Docker.

### Evaluación

`python -m scripts.evaluar_rag` mide sobre 19 preguntas etiquetadas
(`evals/preguntas_rag.jsonl`): hit@k, MRR y tasa de rechazo de preguntas fuera de alcance.
Con esto se calibra `RAG_MIN_SCORE`: subirlo mejora el rechazo pero puede perder respuestas.
Resultado medido con el modelo real (k=3, umbral 0.35): **hit@3 = 0.82 (14/17), MRR = 0.79,
rechazo fuera de alcance = 2/3**. Los fallos (mención de "artículo 76", "bono", "justifico")
muestran el límite de un embedding pequeño solo con señal densa y orientan el siguiente paso:
búsqueda híbrida sobre todo el índice.

## Consecuencias

- ✅ Cero servicios extra, cero costo de embeddings, nada sale de la máquina en la ingesta.
- ✅ Citas exactas por artículo y evaluación reproducible.
- ⚠️ MiniLM es un modelo pequeño: en preguntas coloquiales puede recuperar un artículo
  vecino. Con más tiempo: búsqueda híbrida (BM25 + vectores) y un re-ranker.
- ⚠️ El regex depende del formato del PDF oficial; si cambia, la prueba de chunking y el
  conteo de fragmentos en el log de ingesta lo hacen evidente.
- ⚠️ NumPy y SQLite no escalan a múltiples réplicas con escritura concurrente; para
  producción se movería a Postgres + pgvector (el acceso está aislado en `app/data/db.py` y
  `app/rag/store.py`).
