"""Definición del agente de RRHH con Google ADK."""

from __future__ import annotations

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.genai import types

from app.config import Settings
from app.tools.herramientas import HERRAMIENTAS

NOMBRE_APP = "agente_rrhh"
NOMBRE_AGENTE = "alta_rrhh"
VERSION_PROMPT = "agente_rrhh.v2"


def cargar_prompt(ajustes: Settings, version: str = VERSION_PROMPT) -> str:
    ruta = ajustes.prompts_dir / f"{version}.md"
    return ruta.read_text(encoding="utf-8")


def construir_agente(ajustes: Settings) -> Agent:
    """Un solo agente con 5 tools. Ver ADR-0003 para el porqué de no usar subagentes."""
    extra: dict[str, object] = {"num_retries": ajustes.llm_num_retries}
    if ajustes.llm_fallback_model and ajustes.llm_fallback_model != ajustes.llm_model:
        extra["fallbacks"] = [ajustes.llm_fallback_model]
    if ajustes.llm_reasoning_effort and "gpt-oss" in ajustes.llm_model:
        extra["reasoning_effort"] = ajustes.llm_reasoning_effort
    modelo = LiteLlm(model=ajustes.llm_model, **extra)
    return Agent(
        name=NOMBRE_AGENTE,
        model=modelo,
        description="Responde dudas de RRHH con base en la LFT y el reglamento interno.",
        instruction=cargar_prompt(ajustes),
        tools=list(HERRAMIENTAS),
        generate_content_config=types.GenerateContentConfig(
            temperature=ajustes.llm_temperature,
            max_output_tokens=ajustes.llm_max_tokens,
        ),
    )
