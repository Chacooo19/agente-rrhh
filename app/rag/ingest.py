"""Construye el índice vectorial a partir de la LFT (PDF) y los documentos internos (Markdown).

Uso:
    python -m app.rag.ingest
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from app.config import get_settings
from app.guardrails import detectar_injection, sanear_documento
from app.logging_config import configurar_logging
from app.rag.chunking import Fragmento, fragmentar_lft, fragmentar_markdown
from app.rag.embeddings import Embedder, FastEmbedEmbedder
from app.rag.store import IndiceVectorial

logger = logging.getLogger(__name__)

# Documento interno -> nombre de la fuente con el que se cita
DOCUMENTOS_INTERNOS = {
    "reglamento_interno.md": "Reglamento interno",
    "politica_bonos_2026.md": "Política de bonos",
}


def leer_pdf(ruta: Path) -> str:
    from pypdf import PdfReader

    lector = PdfReader(str(ruta))
    return "\n".join(pagina.extract_text() or "" for pagina in lector.pages)


def cargar_fragmentos(data_dir: Path) -> list[Fragmento]:
    fragmentos: list[Fragmento] = []
    ruta_lft = data_dir / "raw" / "LFT.pdf"
    if ruta_lft.exists():
        fragmentos += fragmentar_lft(leer_pdf(ruta_lft), documento="LFT.pdf")
    else:
        logger.warning("No se encontró la LFT", extra={"ruta": str(ruta_lft)})

    for nombre, fuente in DOCUMENTOS_INTERNOS.items():
        ruta = data_dir / "docs" / nombre
        fragmentos += fragmentar_markdown(
            ruta.read_text(encoding="utf-8"), fuente=fuente, documento=nombre
        )

    # Defensa en ingesta: se quita el contenido oculto (comentarios HTML) y, si el texto
    # visible que queda sigue teniendo instrucciones para la IA, el fragmento se marca como
    # sospechoso y el recuperador lo neutraliza antes de entregarlo al modelo.
    for frag in fragmentos:
        limpio, patrones = sanear_documento(frag.texto)
        if not patrones:
            continue
        frag.texto = limpio
        frag.patrones_sospechosos = patrones
        frag.sospechoso = bool(detectar_injection(limpio))
        logger.warning(
            "Contenido sospechoso detectado en ingesta",
            extra={"fragmento": frag.id, "patrones": patrones, "neutralizado": frag.sospechoso},
        )
    return fragmentos


def construir_indice(data_dir: Path, embedder: Embedder) -> IndiceVectorial:
    fragmentos = cargar_fragmentos(data_dir)
    # Incluimos fuente y título en el texto a vectorizar para que "aguinaldo reglamento"
    # encuentre el artículo correcto aunque el cuerpo no repita esas palabras.
    textos = [f"{f.fuente}. {f.titulo}.\n{f.texto}" for f in fragmentos]
    vectores = embedder.embed(textos)
    return IndiceVectorial(vectores=vectores, fragmentos=fragmentos)


def main() -> None:
    ajustes = get_settings()
    configurar_logging(ajustes.log_level)
    inicio = time.perf_counter()
    indice = construir_indice(ajustes.data_dir, FastEmbedEmbedder(ajustes.embedding_model))
    indice.guardar(ajustes.index_dir)
    sospechosos = sum(f.sospechoso for f in indice.fragmentos)
    logger.info(
        "Índice construido",
        extra={
            "fragmentos": len(indice.fragmentos),
            "sospechosos": sospechosos,
            "segundos": round(time.perf_counter() - inicio, 1),
            "destino": str(ajustes.index_dir),
        },
    )


if __name__ == "__main__":
    main()
