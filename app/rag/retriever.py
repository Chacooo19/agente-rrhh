"""Búsqueda semántica sobre la normativa, con umbral de confianza y filtro anti-injection."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from app.guardrails import TEXTO_NEUTRALIZADO
from app.rag.embeddings import Embedder
from app.rag.store import IndiceVectorial

_MENCION_ARTICULO = re.compile(r"art[íi]culo\s+(\d+(?:\s*bis)?)", re.IGNORECASE)
FUENTES_VALIDAS = {"todas", "LFT", "Reglamento interno", "Política de bonos"}
BONO_MENCION_EXPLICITA = 0.25
# Búsqueda híbrida ligera: el embedding pequeño a veces no prioriza el artículo que contiene
# literalmente la palabra clave ("aguinaldo"); sumamos un bono proporcional a los términos
# de la consulta que aparecen en el fragmento.
BONO_LEXICO = 0.15
_PALABRAS_VACIAS = {
    "cuanto",
    "cuantos",
    "cuantas",
    "donde",
    "cuando",
    "puedo",
    "tengo",
    "quiero",
    "sobre",
    "segun",
    "entre",
    "desde",
    "hasta",
    "porque",
    "tiene",
    "tienen",
    "toca",
    "esta",
    "este",
    "estos",
    "estas",
    "dice",
    "hacer",
    "debo",
    "pueden",
    "puede",
}


def _sin_acentos(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()


def _terminos(consulta: str) -> set[str]:
    palabras = re.findall(r"[a-z0-9]+", _sin_acentos(consulta))
    return {p for p in palabras if len(p) >= 5 and p not in _PALABRAS_VACIAS}


@dataclass
class Resultado:
    id: str
    fuente: str
    articulo: str
    titulo: str
    texto: str
    puntaje: float
    neutralizado: bool
    alertas: list[str]

    def a_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "fuente": self.fuente,
            "articulo": self.articulo,
            "titulo": self.titulo,
            "texto": self.texto,
            "puntaje": round(self.puntaje, 3),
            "neutralizado": self.neutralizado,
            "alertas": self.alertas,
        }


class Recuperador:
    def __init__(
        self, indice: IndiceVectorial, embedder: Embedder, top_k: int = 5, min_score: float = 0.35
    ) -> None:
        self.indice = indice
        self.embedder = embedder
        self.top_k = top_k
        self.min_score = min_score
        self._textos_normalizados = {
            f.id: _sin_acentos(f"{f.titulo} {f.texto}") for f in indice.fragmentos
        }

    def buscar(self, consulta: str, fuente: str = "todas") -> list[Resultado]:
        """Devuelve los fragmentos relevantes con puntaje >= umbral, ya saneados."""
        vector = self.embedder.embed([consulta])[0]
        # Pedimos más candidatos de los necesarios para poder filtrar por fuente
        candidatos = self.indice.buscar(vector, k=self.top_k * 6)
        terminos = _terminos(consulta)
        articulos_mencionados = {
            m.group(1).replace(" ", "").lower() for m in _MENCION_ARTICULO.finditer(consulta)
        }
        resultados: list[Resultado] = []
        for frag, puntaje in candidatos:
            if fuente != "todas" and frag.fuente != fuente:
                continue
            # Si el usuario cita un artículo explícito, ese fragmento sube en el ranking
            if frag.articulo.replace(" ", "").lower() in articulos_mencionados:
                puntaje += BONO_MENCION_EXPLICITA
            if terminos:
                texto = self._textos_normalizados.get(frag.id, "")
                aciertos = sum(t in texto for t in terminos)
                puntaje += BONO_LEXICO * aciertos / len(terminos)
            if puntaje < self.min_score:
                continue
            resultados.append(
                Resultado(
                    id=frag.id,
                    fuente=frag.fuente,
                    articulo=frag.articulo,
                    titulo=frag.titulo,
                    texto=TEXTO_NEUTRALIZADO if frag.sospechoso else frag.texto,
                    puntaje=puntaje,
                    neutralizado=frag.sospechoso,
                    alertas=list(frag.patrones_sospechosos),
                )
            )
        resultados.sort(key=lambda r: r.puntaje, reverse=True)
        return resultados[: self.top_k]
