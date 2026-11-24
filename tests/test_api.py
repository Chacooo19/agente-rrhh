"""Pruebas de la API REST con el agente simulado."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.agent.servicio import ServicioAgente
from app.api.main import crear_app
from app.config import Settings
from app.rag.retriever import Recuperador
from tests.dobles import EjecutorSimulado


@pytest.fixture
def servicio(ajustes: Settings) -> ServicioAgente:
    return ServicioAgente(ajustes, ejecutor=EjecutorSimulado())


@pytest.fixture
def cliente(ajustes: Settings, servicio: ServicioAgente, recuperador: Recuperador) -> TestClient:
    app = crear_app(ajustes, servicio=servicio, recuperador=recuperador)
    with TestClient(app) as c:
        yield c  # type: ignore[misc]


def _token(cliente: TestClient, usuario: str) -> str:
    r = cliente.post("/api/login", json={"usuario": usuario, "password": "demo1234"})
    assert r.status_code == 200, r.text
    return str(r.json()["token"])


def test_login_correcto_e_incorrecto(cliente: TestClient) -> None:
    ok = cliente.post("/api/login", json={"usuario": "E001", "password": "demo1234"})
    assert ok.status_code == 200
    assert ok.json()["rol"] == "rrhh"
    mal = cliente.post("/api/login", json={"usuario": "e001", "password": "otra"})
    assert mal.status_code == 401


def test_chat_requiere_sesion(cliente: TestClient) -> None:
    assert cliente.post("/api/chat", json={"mensaje": "hola"}).status_code == 401
    r = cliente.post(
        "/api/chat", json={"mensaje": "hola"}, headers={"Authorization": "Bearer basura"}
    )
    assert r.status_code == 401


def test_chat_devuelve_respuesta_con_traza(cliente: TestClient) -> None:
    token = _token(cliente, "e005")
    r = cliente.post(
        "/api/chat",
        json={"mensaje": "¿Cuánto aguinaldo me toca?"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["respuesta"].startswith("Te corresponden")
    assert cuerpo["fuentes"][0]["articulo"] == "7"
    assert cuerpo["traza"][0]["nombre"] == "buscar_normativa"


def test_chat_modelo_caido_devuelve_503(ajustes: Settings, recuperador: Recuperador) -> None:
    servicio = ServicioAgente(ajustes, ejecutor=EjecutorSimulado(falla=TimeoutError()))
    with TestClient(crear_app(ajustes, servicio=servicio, recuperador=recuperador)) as c:
        token = _token(c, "e005")
        r = c.post(
            "/api/chat", json={"mensaje": "hola"}, headers={"Authorization": f"Bearer {token}"}
        )
    assert r.status_code == 503
    assert "tardó" in r.json()["detail"]


def test_tickets_solo_para_rrhh(cliente: TestClient) -> None:
    empleado = {"Authorization": f"Bearer {_token(cliente, 'e005')}"}
    rrhh = {"Authorization": f"Bearer {_token(cliente, 'e001')}"}
    assert cliente.get("/api/tickets", headers=empleado).status_code == 403
    assert cliente.get("/api/tickets", headers=rrhh).status_code == 200


def test_salud(cliente: TestClient) -> None:
    r = cliente.get("/api/salud").json()
    assert r["indice_cargado"] is True
    assert r["llm_configurado"] is False
