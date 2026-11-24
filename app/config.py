"""Configuración central del proyecto, leída de variables de entorno (.env)."""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Valores configurables. Los secretos solo llegan por entorno, nunca por código."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Modelo de lenguaje
    llm_model: str = "groq/openai/gpt-oss-120b"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 1024
    # Si el modelo principal responde 429 (límite por minuto), LiteLLM reintenta con espera
    # exponencial y luego prueba este modelo (en Groq los límites son por modelo).
    llm_fallback_model: str = "groq/openai/gpt-oss-20b"
    llm_num_retries: int = 3
    # gpt-oss razona antes de responder; "low" gasta menos tokens y responde más rápido
    llm_reasoning_effort: str = "low"
    groq_api_key: str = ""
    ollama_api_base: str = ""

    # Seguridad
    jwt_secret: str = Field(default="dev-inseguro-cambiar", min_length=8)
    jwt_expires_minutes: int = 120
    demo_password: str = "demo1234"

    # RAG
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    rag_top_k: int = 3
    rag_min_score: float = 0.35

    # Rutas
    data_dir: Path = RAIZ / "data"
    prompts_dir: Path = RAIZ / "prompts"
    db_path: Path = RAIZ / "data" / "rrhh.db"
    index_dir: Path = RAIZ / "data" / "index"

    fecha_referencia: date | None = None
    log_level: str = "INFO"

    @field_validator("fecha_referencia", mode="before")
    @classmethod
    def _vacio_es_none(cls, valor: object) -> object:
        return None if valor in ("", None) else valor

    def hoy(self) -> date:
        """Fecha usada para calcular antigüedad; configurable para demos reproducibles."""
        return self.fecha_referencia or date.today()

    def llm_configurado(self) -> bool:
        """Indica si hay credenciales/endpoint para el proveedor elegido."""
        if self.llm_model.startswith("groq/"):
            return bool(self.groq_api_key)
        return True


@lru_cache
def get_settings() -> Settings:
    return Settings()
