from typing import Any

from app.tools.contexto import Dependencias
from app.tools.herramientas import (
    buscar_normativa,
    calcular_prestaciones,
    consultar_empleado,
    crear_ticket_rrhh,
    listar_tickets,
)
from tests.conftest import ContextoFalso, contexto

ctx: Any  # los ContextoFalso se pasan donde ADK pasaría un ToolContext


def test_empleado_consulta_su_propio_expediente(dependencias: Dependencias) -> None:
    r = consultar_empleado("", contexto("E005"))  # type: ignore[arg-type]
    assert r["ok"]
    assert r["empleado"]["id_empleado"] == "E005"


def test_empleado_no_puede_ver_expediente_ajeno(dependencias: Dependencias) -> None:
    r = consultar_empleado("E010", contexto("E005"))  # type: ignore[arg-type]
    assert r == {"ok": False, "error": "no_autorizado", "mensaje": r["mensaje"]}
    assert "salario_diario" not in str(r)


def test_rrhh_puede_ver_cualquier_expediente(dependencias: Dependencias) -> None:
    r = consultar_empleado("e010", contexto("E001", "rrhh"))  # type: ignore[arg-type]
    assert r["ok"]
    assert r["empleado"]["id_empleado"] == "E010"


def test_empleado_inexistente(dependencias: Dependencias) -> None:
    r = consultar_empleado("E999", contexto("E001", "rrhh"))  # type: ignore[arg-type]
    assert r["error"] == "no_encontrado"


def test_sin_sesion_autenticada_no_hay_datos(dependencias: Dependencias) -> None:
    r = consultar_empleado("E005", ContextoFalso())  # type: ignore[arg-type]
    assert r["error"] == "sin_sesion"


def test_calcular_prestaciones_respeta_permisos(dependencias: Dependencias) -> None:
    propio = calcular_prestaciones("", "todas", contexto("E009"))  # type: ignore[arg-type]
    assert propio["ok"]
    assert {"vacaciones", "aguinaldo"} <= propio.keys()
    ajeno = calcular_prestaciones("E004", "vacaciones", contexto("E009"))  # type: ignore[arg-type]
    assert ajeno["error"] == "no_autorizado"


def test_calcular_prestaciones_concepto_invalido_usa_todas(dependencias: Dependencias) -> None:
    r = calcular_prestaciones("", "bonos", contexto("E009"))  # type: ignore[arg-type]
    assert {"vacaciones", "aguinaldo"} <= r.keys()


def test_crear_ticket_y_solo_rrhh_lo_lista(dependencias: Dependencias) -> None:
    r = crear_ticket_rrhh(
        "Duda de nómina",
        "Me descontaron un día",
        "urgente",
        contexto("E005"),  # type: ignore[arg-type]
    )
    assert r["ok"] and r["folio"] >= 1
    assert r["prioridad"] == "media"  # prioridad inválida se normaliza
    assert listar_tickets("todos", contexto("E005"))["error"] == "no_autorizado"  # type: ignore[arg-type]
    lista = listar_tickets("abierto", contexto("E001", "rrhh"))  # type: ignore[arg-type]
    assert lista["total"] == 1


def test_ticket_requiere_asunto_y_detalle(dependencias: Dependencias) -> None:
    r = crear_ticket_rrhh(" ", "", "alta", contexto("E005"))  # type: ignore[arg-type]
    assert r["error"] == "datos_incompletos"


def test_buscar_normativa_devuelve_fragmentos_citables(dependencias: Dependencias) -> None:
    r = buscar_normativa("prima vacacional", "todas", contexto("E005"))  # type: ignore[arg-type]
    assert r["ok"] and r["encontrado"]
    assert {"id", "fuente", "articulo", "texto"} <= r["fragmentos"][0].keys()


def test_buscar_normativa_sin_indice(dependencias: Dependencias) -> None:
    dependencias.recuperador = None
    r = buscar_normativa("vacaciones", "todas", contexto("E005"))  # type: ignore[arg-type]
    assert r["error"] == "rag_no_disponible"
