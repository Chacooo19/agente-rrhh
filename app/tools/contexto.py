"""Acceso a las dependencias de las tools y a la identidad de quien pregunta.

La identidad (id de empleado y rol) la escribe el backend en el estado de la sesión de ADK
al crearla, a partir del token JWT. El modelo no puede modificarla: así la autorización no
depende de lo que el modelo "decida", sino del código.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.config import Settings
from app.data.db import BaseDatos
from app.rag.retriever import Recuperador

CLAVE_ID_EMPLEADO = "id_empleado_actual"
CLAVE_ROL = "rol_actual"
ROL_RRHH = "rrhh"


class ConEstado(Protocol):
    @property
    def state(self) -> Any: ...


@dataclass
class Dependencias:
    db: BaseDatos
    recuperador: Recuperador | None
    ajustes: Settings


_dependencias: Dependencias | None = None


def configurar_dependencias(dependencias: Dependencias) -> None:
    global _dependencias
    _dependencias = dependencias


def deps() -> Dependencias:
    if _dependencias is None:
        raise RuntimeError("Las dependencias de las tools no se han configurado")
    return _dependencias


@dataclass(frozen=True)
class Solicitante:
    id_empleado: str
    rol: str

    @property
    def es_rrhh(self) -> bool:
        return self.rol == ROL_RRHH

    def puede_ver(self, id_empleado: str) -> bool:
        return self.es_rrhh or id_empleado.upper() == self.id_empleado.upper()


class SinIdentidadError(PermissionError):
    pass


def solicitante(tool_context: ConEstado) -> Solicitante:
    estado = tool_context.state
    id_empleado, rol = estado.get(CLAVE_ID_EMPLEADO), estado.get(CLAVE_ROL)
    if not id_empleado or not rol:
        raise SinIdentidadError("La sesión no tiene un usuario autenticado")
    return Solicitante(id_empleado=str(id_empleado), rol=str(rol))


def error(codigo: str, mensaje: str) -> dict[str, Any]:
    """Formato uniforme de error que el modelo sabe interpretar (ver prompt)."""
    return {"ok": False, "error": codigo, "mensaje": mensaje}
