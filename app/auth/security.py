"""Hash de contraseñas (scrypt de la librería estándar) y tokens JWT firmados."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

_N, _R, _P = 2**14, 8, 1
ALGORITMO_JWT = "HS256"


class TokenInvalidoError(Exception):
    pass


def hashear_password(password: str) -> str:
    sal = secrets.token_bytes(16)
    derivada = hashlib.scrypt(password.encode(), salt=sal, n=_N, r=_R, p=_P)
    return "scrypt$" + base64.b64encode(sal).decode() + "$" + base64.b64encode(derivada).decode()


def verificar_password(password: str, almacenado: str) -> bool:
    try:
        _, sal_b64, hash_b64 = almacenado.split("$")
        sal, esperado = base64.b64decode(sal_b64), base64.b64decode(hash_b64)
    except ValueError:
        return False
    derivada = hashlib.scrypt(password.encode(), salt=sal, n=_N, r=_R, p=_P)
    return hmac.compare_digest(derivada, esperado)


def crear_token(datos: dict[str, Any], secreto: str, minutos: int) -> str:
    carga = {**datos, "exp": datetime.now(UTC) + timedelta(minutes=minutos)}
    return jwt.encode(carga, secreto, algorithm=ALGORITMO_JWT)


def leer_token(token: str, secreto: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, secreto, algorithms=[ALGORITMO_JWT])
    except jwt.PyJWTError as error:
        raise TokenInvalidoError(str(error)) from error
