"""Índice vectorial en disco: una matriz NumPy + metadatos JSON.

Con ~1,100 fragmentos la búsqueda exacta por producto punto tarda milisegundos, así que
no se justifica un servidor vectorial (Qdrant, pgvector) para este volumen. Ver ADR-0004.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.rag.chunking import Fragmento
from app.rag.embeddings import Matriz

ARCHIVO_VECTORES = "vectores.npy"
ARCHIVO_METADATOS = "fragmentos.json"


class IndiceNoEncontradoError(RuntimeError):
    """El índice no se ha construido todavía (falta correr la ingesta)."""


@dataclass
class IndiceVectorial:
    vectores: Matriz
    fragmentos: list[Fragmento]

    def guardar(self, directorio: Path) -> None:
        directorio.mkdir(parents=True, exist_ok=True)
        np.save(directorio / ARCHIVO_VECTORES, self.vectores)
        datos = [f.a_dict() for f in self.fragmentos]
        (directorio / ARCHIVO_METADATOS).write_text(
            json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8"
        )

    @classmethod
    def cargar(cls, directorio: Path) -> IndiceVectorial:
        ruta_v, ruta_m = directorio / ARCHIVO_VECTORES, directorio / ARCHIVO_METADATOS
        if not ruta_v.exists() or not ruta_m.exists():
            raise IndiceNoEncontradoError(
                f"No existe el índice en {directorio}. Ejecuta: python -m app.rag.ingest"
            )
        vectores = np.load(ruta_v).astype(np.float32)
        fragmentos = [Fragmento(**d) for d in json.loads(ruta_m.read_text(encoding="utf-8"))]
        return cls(vectores=vectores, fragmentos=fragmentos)

    def buscar(self, consulta: Matriz, k: int) -> list[tuple[Fragmento, float]]:
        """Similitud coseno (los vectores ya vienen normalizados)."""
        puntajes = self.vectores @ consulta.reshape(-1)
        orden = np.argsort(-puntajes)[:k]
        return [(self.fragmentos[i], float(puntajes[i])) for i in orden]
