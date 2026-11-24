"""Logs estructurados en JSON: una línea por evento, fácil de filtrar o enviar a un colector."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

_CAMPOS_ESTANDAR = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}


class FormateadorJSON(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        datos: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "nivel": record.levelname,
            "logger": record.name,
            "mensaje": record.getMessage(),
        }
        # Campos extra pasados con logger.info("...", extra={...})
        for clave, valor in record.__dict__.items():
            if clave not in _CAMPOS_ESTANDAR:
                datos[clave] = valor
        if record.exc_info:
            datos["error"] = self.formatException(record.exc_info)
        return json.dumps(datos, ensure_ascii=False, default=str)


def configurar_logging(nivel: str = "INFO") -> None:
    manejador = logging.StreamHandler(sys.stdout)
    manejador.setFormatter(FormateadorJSON())
    raiz = logging.getLogger()
    raiz.handlers = [manejador]
    raiz.setLevel(nivel.upper())
    # LiteLLM es muy ruidoso en INFO
    logging.getLogger("LiteLLM").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
