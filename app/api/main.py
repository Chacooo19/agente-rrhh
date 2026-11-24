"""API REST (FastAPI) y servidor de la interfaz web."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles

from app.agent.servicio import AgenteNoDisponibleError, ServicioAgente
from app.api.esquemas import (
    ErrorApi,
    RespuestaChat,
    RespuestaLogin,
    Salud,
    SolicitudChat,
    SolicitudLogin,
    TicketSalida,
)
from app.auth.security import TokenInvalidoError, crear_token, leer_token, verificar_password
from app.config import Settings, get_settings
from app.data.db import BaseDatos
from app.logging_config import configurar_logging
from app.rag.embeddings import FastEmbedEmbedder
from app.rag.retriever import Recuperador
from app.rag.store import IndiceNoEncontradoError, IndiceVectorial
from app.tools.contexto import Dependencias, configurar_dependencias

logger = logging.getLogger(__name__)
DIR_WEB = Path(__file__).resolve().parent.parent / "web"

esquema_bearer = HTTPBearer(auto_error=False)


def usuario_actual(
    request: Request,
    credenciales: Annotated[HTTPAuthorizationCredentials | None, Depends(esquema_bearer)],
) -> dict[str, str]:
    """Valida el token Bearer y devuelve la identidad de quien llama."""
    if credenciales is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Inicia sesión para continuar")
    ajustes: Settings = request.app.state.ajustes
    try:
        datos = leer_token(credenciales.credentials, ajustes.jwt_secret)
    except TokenInvalidoError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesión expirada o inválida") from e
    return {k: str(datos[k]) for k in ("sub", "rol", "id_empleado", "nombre")}


UsuarioSesion = Annotated[dict[str, str], Depends(usuario_actual)]


def crear_recuperador(ajustes: Settings) -> Recuperador | None:
    try:
        indice = IndiceVectorial.cargar(ajustes.index_dir)
    except IndiceNoEncontradoError as e:
        logger.error("RAG deshabilitado", extra={"motivo": str(e)})
        return None
    return Recuperador(
        indice,
        FastEmbedEmbedder(ajustes.embedding_model),
        top_k=ajustes.rag_top_k,
        min_score=ajustes.rag_min_score,
    )


def crear_app(
    ajustes: Settings | None = None,
    servicio: ServicioAgente | None = None,
    recuperador: Recuperador | None = None,
    cargar_rag: bool = True,
) -> FastAPI:
    """Fábrica de la app. Los parámetros permiten inyectar dobles de prueba."""
    ajustes = ajustes or get_settings()

    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI) -> AsyncIterator[None]:
        configurar_logging(ajustes.log_level)
        db = BaseDatos(ajustes.db_path)
        db.inicializar(ajustes.data_dir / "seed" / "empleados.csv", ajustes.demo_password)
        rec = (
            recuperador if recuperador is not None or not cargar_rag else crear_recuperador(ajustes)
        )
        configurar_dependencias(Dependencias(db=db, recuperador=rec, ajustes=ajustes))
        app.state.ajustes = ajustes
        app.state.db = db
        app.state.recuperador = rec
        app.state.servicio = servicio or ServicioAgente(ajustes)
        if not ajustes.llm_configurado():
            logger.warning("Falta la API key del modelo", extra={"modelo": ajustes.llm_model})
        logger.info("API lista", extra={"modelo": ajustes.llm_model, "rag": rec is not None})
        yield

    app = FastAPI(
        title="Agente RRHH — Grupo Altavista",
        version="1.0.0",
        description="Asistente de RRHH basado en la LFT y un reglamento interno (datos ficticios).",
        lifespan=ciclo_de_vida,
    )

    @app.post("/api/login", response_model=RespuestaLogin, responses={401: {"model": ErrorApi}})
    def login(solicitud: SolicitudLogin, request: Request) -> RespuestaLogin:
        db: BaseDatos = request.app.state.db
        usuario = db.obtener_usuario(solicitud.usuario)
        if usuario is None or not verificar_password(solicitud.password, usuario.password_hash):
            logger.info("Login fallido", extra={"usuario": solicitud.usuario})
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario o contraseña incorrectos")
        empleado = db.obtener_empleado(usuario.id_empleado)
        nombre = empleado.nombre if empleado else usuario.usuario
        token = crear_token(
            {
                "sub": usuario.usuario,
                "rol": usuario.rol,
                "id_empleado": usuario.id_empleado,
                "nombre": nombre,
            },
            ajustes.jwt_secret,
            ajustes.jwt_expires_minutes,
        )
        return RespuestaLogin(
            token=token,
            usuario=usuario.usuario,
            nombre=nombre,
            rol=usuario.rol,
            id_empleado=usuario.id_empleado,
        )

    @app.post(
        "/api/chat",
        response_model=RespuestaChat,
        responses={401: {"model": ErrorApi}, 503: {"model": ErrorApi}},
    )
    async def chat(
        solicitud: SolicitudChat, usuario: UsuarioSesion, request: Request
    ) -> RespuestaChat:
        servicio_agente: ServicioAgente = request.app.state.servicio
        try:
            r = await servicio_agente.conversar(
                usuario=usuario["sub"],
                id_empleado=usuario["id_empleado"],
                rol=usuario["rol"],
                mensaje=solicitud.mensaje,
                session_id=solicitud.session_id,
            )
        except AgenteNoDisponibleError as e:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e)) from e
        return RespuestaChat(
            session_id=r.session_id,
            respuesta=r.texto,
            fuentes=r.fuentes,  # type: ignore[arg-type]
            traza=[asdict(p) for p in r.traza],  # type: ignore[misc]
            alertas=r.alertas,
            latencia_ms=r.latencia_ms,
            tokens_entrada=r.tokens_entrada,
            tokens_salida=r.tokens_salida,
            modelo=r.modelo,
            version_prompt=r.version_prompt,
        )

    @app.get(
        "/api/tickets", response_model=list[TicketSalida], responses={403: {"model": ErrorApi}}
    )
    def tickets(usuario: UsuarioSesion, request: Request) -> list[TicketSalida]:
        if usuario["rol"] != "rrhh":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo RRHH puede ver los tickets")
        db: BaseDatos = request.app.state.db
        return [TicketSalida(**asdict(t)) for t in db.listar_tickets()]

    @app.get("/api/salud", response_model=Salud)
    def salud(request: Request) -> Salud:
        rec: Recuperador | None = request.app.state.recuperador
        return Salud(
            estado="ok",
            modelo=ajustes.llm_model,
            llm_configurado=ajustes.llm_configurado(),
            indice_cargado=rec is not None,
            fragmentos_indexados=len(rec.indice.fragmentos) if rec else 0,
        )

    @app.get("/", include_in_schema=False)
    def inicio() -> FileResponse:
        return FileResponse(DIR_WEB / "index.html")

    app.mount("/static", StaticFiles(directory=DIR_WEB), name="static")
    return app


app = crear_app()
