"""Modelos de embeddings detrás de una interfaz mínima, para poder simularlos en pruebas."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from typing import Protocol

import numpy as np
import numpy.typing as npt

Matriz = npt.NDArray[np.float32]


class Embedder(Protocol):
    def embed(self, textos: Sequence[str]) -> Matriz:
        """Devuelve una matriz (n, d) con vectores normalizados (norma 1)."""
        ...


def _normalizar(m: Matriz) -> Matriz:
    normas = np.linalg.norm(m, axis=1, keepdims=True)
    normas[normas == 0] = 1.0
    return (m / normas).astype(np.float32)


class FastEmbedEmbedder:
    """Embeddings multilingües locales con FastEmbed (ONNX, sin PyTorch: imagen ligera).

    El modelo por defecto, paraphrase-multilingual-MiniLM-L12-v2, entiende español, pesa
    ~220 MB y corre en CPU, así que no hay costo por consulta ni se envía texto a terceros.
    """

    def __init__(self, modelo: str) -> None:
        from fastembed import TextEmbedding  # import diferido: es pesado

        self._modelo = TextEmbedding(model_name=modelo)

    def embed(self, textos: Sequence[str]) -> Matriz:
        vectores = np.array(list(self._modelo.embed(list(textos))), dtype=np.float32)
        return _normalizar(vectores)


class HashEmbedder:
    """Embedder determinista basado en bolsa de palabras con hashing.

    Solo para pruebas automáticas: no necesita descargar modelos ni red.
    """

    def __init__(self, dimension: int = 256) -> None:
        self.dimension = dimension

    def embed(self, textos: Sequence[str]) -> Matriz:
        matriz = np.zeros((len(textos), self.dimension), dtype=np.float32)
        for i, texto in enumerate(textos):
            for palabra in re.findall(r"\w+", texto.lower()):
                h = int(hashlib.md5(palabra.encode()).hexdigest(), 16)
                matriz[i, h % self.dimension] += 1.0
        return _normalizar(matriz)
