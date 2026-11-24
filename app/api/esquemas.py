"""Contrato de la API REST (modelos de entrada y salida)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SolicitudLogin(BaseModel):
    usuario: str = Field(min_length=1, max_length=50, examples=["e005"])
    password: str = Field(min_length=1, max_length=200, examples=["demo1234"])


class RespuestaLogin(BaseModel):
    token: str
    usuario: str
    nombre: str
    rol: str
    id_empleado: str


class SolicitudChat(BaseModel):
    mensaje: str = Field(
        min_length=1, max_length=2000, examples=["¿Cuántos días de vacaciones me quedan?"]
    )
    session_id: str | None = Field(
        default=None, max_length=64, description="Omitir para iniciar una conversación nueva"
    )


class Paso(BaseModel):
    tipo: str
    nombre: str
    detalle: dict[str, Any]


class Fuente(BaseModel):
    id: str
    fuente: str
    articulo: str


class RespuestaChat(BaseModel):
    session_id: str
    respuesta: str
    fuentes: list[Fuente]
    traza: list[Paso]
    alertas: list[str]
    latencia_ms: int
    tokens_entrada: int
    tokens_salida: int
    modelo: str
    version_prompt: str


class TicketSalida(BaseModel):
    folio: int
    id_empleado: str
    asunto: str
    detalle: str
    prioridad: str
    estado: str
    creado_en: str


class Salud(BaseModel):
    estado: str
    modelo: str
    llm_configurado: bool
    indice_cargado: bool
    fragmentos_indexados: int


class ErrorApi(BaseModel):
    detail: str
