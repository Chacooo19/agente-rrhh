"""Orquesta un turno de conversación: sesión ADK → agente → traza → respuesta."""

from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol

from google.adk.runners import Runner
from google.adk.sessions import BaseSessionService, InMemorySessionService
from google.genai import types

from app.agent.agente import NOMBRE_APP, VERSION_PROMPT, construir_agente
from app.config import Settings
from app.guardrails import detectar_injection
from app.tools.contexto import CLAVE_ID_EMPLEADO, CLAVE_ROL

logger = logging.getLogger(__name__)

TIEMPO_MAXIMO_SEGUNDOS = 90
MAX_CARACTERES_MENSAJE = 2000


class AgenteNoDisponibleError(RuntimeError):
    """El modelo no respondió (sin API key, límite de uso, red, timeout...)."""


class EjecutorEventos(Protocol):
    def run_async(self, **kwargs: Any) -> AsyncIterator[Any]: ...


@dataclass
class PasoTraza:
    tipo: str  # "tool_llamada" | "tool_resultado" | "alerta"
    nombre: str
    detalle: dict[str, Any]


@dataclass
class RespuestaAgente:
    session_id: str
    texto: str
    traza: list[PasoTraza] = field(default_factory=list)
    fuentes: list[dict[str, str]] = field(default_factory=list)
    alertas: list[str] = field(default_factory=list)
    latencia_ms: int = 0
    tokens_entrada: int = 0
    tokens_salida: int = 0
    modelo: str = ""
    version_prompt: str = VERSION_PROMPT


def _exportar_credenciales(ajustes: Settings) -> None:
    """LiteLLM lee las credenciales del entorno; las pasamos desde la configuración."""
    if ajustes.groq_api_key:
        os.environ.setdefault("GROQ_API_KEY", ajustes.groq_api_key)
    if ajustes.ollama_api_base:
        os.environ.setdefault("OLLAMA_API_BASE", ajustes.ollama_api_base)


def _resumir(valor: Any, limite: int = 600) -> Any:
    """Recorta textos largos para que la traza sea legible en la interfaz y en los logs."""
    if isinstance(valor, str) and len(valor) > limite:
        return valor[:limite] + "…"
    if isinstance(valor, dict):
        return {k: _resumir(v, limite) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_resumir(v, limite) for v in valor[:10]]
    return valor


class ServicioAgente:
    def __init__(
        self,
        ajustes: Settings,
        sesiones: BaseSessionService | None = None,
        ejecutor: EjecutorEventos | None = None,
    ) -> None:
        self.ajustes = ajustes
        self.sesiones = sesiones or InMemorySessionService()
        self.ejecutor: EjecutorEventos
        if ejecutor is not None:
            self.ejecutor = ejecutor
        else:
            _exportar_credenciales(ajustes)
            self.ejecutor = Runner(  # type: ignore[assignment]
                app_name=NOMBRE_APP,
                agent=construir_agente(ajustes),
                session_service=self.sesiones,
            )

    async def _obtener_sesion(
        self, usuario: str, id_empleado: str, rol: str, session_id: str | None
    ) -> str:
        """Recupera la sesión del usuario o crea una nueva con su identidad en el estado.

        Las sesiones se buscan por (usuario, session_id): un usuario no puede retomar la
        conversación de otro aunque conozca su session_id.
        """
        if session_id:
            existente = await self.sesiones.get_session(
                app_name=NOMBRE_APP, user_id=usuario, session_id=session_id
            )
            if existente is not None:
                return session_id
        nueva = await self.sesiones.create_session(
            app_name=NOMBRE_APP,
            user_id=usuario,
            session_id=session_id or uuid.uuid4().hex,
            state={CLAVE_ID_EMPLEADO: id_empleado, CLAVE_ROL: rol},
        )
        return nueva.id

    async def conversar(
        self, usuario: str, id_empleado: str, rol: str, mensaje: str, session_id: str | None
    ) -> RespuestaAgente:
        mensaje = mensaje.strip()[:MAX_CARACTERES_MENSAJE]
        sid = await self._obtener_sesion(usuario, id_empleado, rol, session_id)
        respuesta = RespuestaAgente(session_id=sid, texto="", modelo=self.ajustes.llm_model)

        patrones = detectar_injection(mensaje)
        if patrones:
            respuesta.alertas.append(
                "Posible prompt injection en el mensaje del usuario: " + ", ".join(patrones)
            )
            respuesta.traza.append(
                PasoTraza("alerta", "entrada_sospechosa", {"patrones": patrones})
            )

        inicio = time.perf_counter()
        try:
            await asyncio.wait_for(
                self._ejecutar(usuario, sid, mensaje, respuesta), timeout=TIEMPO_MAXIMO_SEGUNDOS
            )
        except TimeoutError as e:
            raise AgenteNoDisponibleError("El modelo tardó demasiado en responder.") from e
        except AgenteNoDisponibleError:
            raise
        except Exception as e:
            logger.exception("Fallo al ejecutar el agente")
            raise AgenteNoDisponibleError(_mensaje_error_modelo(e)) from e
        respuesta.latencia_ms = int((time.perf_counter() - inicio) * 1000)

        if not respuesta.texto:
            respuesta.texto = (
                "No pude generar una respuesta. Intenta reformular tu pregunta o pide que "
                "escale tu caso a RRHH."
            )
        logger.info(
            "Turno completado",
            extra={
                "usuario": usuario,
                "session_id": sid,
                "tools": [p.nombre for p in respuesta.traza if p.tipo == "tool_llamada"],
                "fuentes": [f["id"] for f in respuesta.fuentes],
                "alertas": respuesta.alertas,
                "latencia_ms": respuesta.latencia_ms,
                "tokens_entrada": respuesta.tokens_entrada,
                "tokens_salida": respuesta.tokens_salida,
                "modelo": respuesta.modelo,
                "version_prompt": respuesta.version_prompt,
            },
        )
        return respuesta

    async def _ejecutar(
        self, usuario: str, sid: str, mensaje: str, respuesta: RespuestaAgente
    ) -> None:
        contenido = types.Content(role="user", parts=[types.Part(text=mensaje)])
        async for evento in self.ejecutor.run_async(
            user_id=usuario, session_id=sid, new_message=contenido
        ):
            uso = getattr(evento, "usage_metadata", None)
            if uso is not None:
                respuesta.tokens_entrada += uso.prompt_token_count or 0
                respuesta.tokens_salida += uso.candidates_token_count or 0
            for llamada in evento.get_function_calls() or []:
                respuesta.traza.append(
                    PasoTraza("tool_llamada", llamada.name or "", dict(llamada.args or {}))
                )
            for resultado in evento.get_function_responses() or []:
                datos = dict(resultado.response or {})
                respuesta.traza.append(
                    PasoTraza("tool_resultado", resultado.name or "", _resumir(datos))
                )
                _registrar_fuentes(datos, respuesta)
            if evento.is_final_response() and evento.content and evento.content.parts:
                texto = "".join(p.text or "" for p in evento.content.parts if not p.thought)
                if texto.strip():
                    respuesta.texto = texto.strip()


def _registrar_fuentes(datos: dict[str, Any], respuesta: RespuestaAgente) -> None:
    """Extrae las citas de los resultados de buscar_normativa y sus alertas de seguridad."""
    vistos = {f["id"] for f in respuesta.fuentes}
    for frag in datos.get("fragmentos", []) or []:
        if frag.get("id") not in vistos:
            respuesta.fuentes.append(
                {"id": frag["id"], "fuente": frag["fuente"], "articulo": frag["articulo"]}
            )
            vistos.add(frag["id"])
        if frag.get("neutralizado") or frag.get("alertas"):
            alerta = (
                f"Se eliminó contenido sospechoso en {frag['fuente']} art. {frag['articulo']} "
                f"({', '.join(frag.get('alertas') or ['neutralizado'])})"
            )
            if alerta not in respuesta.alertas:
                respuesta.alertas.append(alerta)
    if datos.get("error") == "no_autorizado":
        alerta = "Una tool negó el acceso a datos de otra persona (autorización en código)"
        if alerta not in respuesta.alertas:
            respuesta.alertas.append(alerta)


def _mensaje_error_modelo(error: Exception) -> str:
    nombre = type(error).__name__
    if "Authentication" in nombre or "api_key" in str(error).lower():
        return "No hay una API key válida para el modelo. Revisa GROQ_API_KEY en tu .env."
    if "RateLimit" in nombre:
        return (
            "Se alcanzó el límite de tokens por minuto del proveedor del modelo (en la capa "
            "gratuita de Groq son 8,000 por minuto). Espera un minuto e intenta de nuevo."
        )
    if "Connection" in nombre or "Timeout" in nombre:
        return "No se pudo conectar con el proveedor del modelo. Revisa tu conexión."
    return "El modelo no está disponible en este momento. Intenta de nuevo."
