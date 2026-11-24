from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from app.config import RAIZ, Settings
from app.data.db import BaseDatos
from app.rag.embeddings import HashEmbedder
from app.rag.ingest import construir_indice
from app.rag.retriever import Recuperador
from app.tools.contexto import CLAVE_ID_EMPLEADO, CLAVE_ROL, Dependencias, configurar_dependencias

FECHA_PRUEBAS = date(2026, 11, 24)


@dataclass
class ContextoFalso:
    """Sustituye a ToolContext de ADK: solo necesitamos el estado de la sesión."""

    state: dict[str, Any] = field(default_factory=dict)


def contexto(id_empleado: str, rol: str = "empleado") -> ContextoFalso:
    return ContextoFalso(state={CLAVE_ID_EMPLEADO: id_empleado, CLAVE_ROL: rol})


@pytest.fixture
def ajustes(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        db_path=tmp_path / "prueba.db",
        index_dir=tmp_path / "index",
        fecha_referencia=FECHA_PRUEBAS,
        jwt_secret="secreto-de-pruebas-con-32-bytes-o-mas",
        groq_api_key="",
        rag_min_score=0.05,
    )


@pytest.fixture
def db(ajustes: Settings) -> BaseDatos:
    base = BaseDatos(ajustes.db_path)
    base.inicializar(RAIZ / "data" / "seed" / "empleados.csv", "demo1234")
    return base


@pytest.fixture
def recuperador(ajustes: Settings, tmp_path: Path) -> Recuperador:
    # Índice solo con los documentos internos (sin el PDF de la LFT) y embeddings de prueba
    data = tmp_path / "data"
    (data / "docs").mkdir(parents=True)
    for nombre in ("reglamento_interno.md", "politica_bonos_2026.md"):
        (data / "docs" / nombre).write_text(
            (RAIZ / "data" / "docs" / nombre).read_text(encoding="utf-8"), encoding="utf-8"
        )
    indice = construir_indice(data, HashEmbedder())
    return Recuperador(indice, HashEmbedder(), top_k=3, min_score=0.05)


@pytest.fixture
def dependencias(db: BaseDatos, recuperador: Recuperador, ajustes: Settings) -> Dependencias:
    deps = Dependencias(db=db, recuperador=recuperador, ajustes=ajustes)
    configurar_dependencias(deps)
    return deps
