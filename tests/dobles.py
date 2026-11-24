"""Dobles de prueba: simulan el Runner de ADK sin llamar a ningún modelo real."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from google.adk.events import Event
from google.genai import types


def _evento(*partes: types.Part) -> Event:
    return Event(author="alta_rrhh", content=types.Content(role="model", parts=list(partes)))


class EjecutorSimulado:
    """Reproduce lo que haría el Runner de ADK: llama una tool y luego responde."""

    def __init__(
        self,
        falla: Exception | None = None,
        texto: str = "Te corresponden 20 días (Reglamento interno, art. 7).",
    ) -> None:
        self.falla = falla
        self.texto = texto
        self.llamadas: list[dict[str, Any]] = []

    async def run_async(self, **kwargs: Any) -> AsyncIterator[Event]:
        self.llamadas.append(kwargs)
        if self.falla:
            raise self.falla
        yield _evento(
            types.Part(
                function_call=types.FunctionCall(
                    name="buscar_normativa", args={"consulta": "aguinaldo", "fuente": "todas"}
                )
            )
        )
        yield _evento(
            types.Part(
                function_response=types.FunctionResponse(
                    name="buscar_normativa",
                    response={
                        "ok": True,
                        "encontrado": True,
                        "fragmentos": [
                            {
                                "id": "reglamento-interno-art7",
                                "fuente": "Reglamento interno",
                                "articulo": "7",
                                "texto": "20 días",
                                "neutralizado": False,
                                "alertas": [],
                            },
                            {
                                "id": "politica-de-bonos-art2",
                                "fuente": "Política de bonos",
                                "articulo": "2",
                                "texto": "...",
                                "neutralizado": False,
                                "alertas": ["contenido_oculto_html"],
                            },
                        ],
                    },
                )
            )
        )
        yield _evento(types.Part(text=self.texto))
