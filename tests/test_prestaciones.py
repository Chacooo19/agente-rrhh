from datetime import date

import pytest

from app.tools import prestaciones as p


@pytest.mark.parametrize(
    ("anios", "dias"),
    [
        (0, 0),
        (1, 12),
        (2, 14),
        (3, 16),
        (4, 18),
        (5, 20),
        (6, 22),
        (10, 22),
        (11, 24),
        (15, 24),
        (16, 26),
        (21, 28),
        (31, 32),
    ],
)
def test_dias_vacaciones_por_ley_articulo_76(anios: int, dias: int) -> None:
    assert p.dias_vacaciones_por_ley(anios) == dias


def test_anios_cumplidos_respeta_aniversario() -> None:
    assert p.anios_cumplidos(date(2020, 12, 1), date(2026, 11, 30)) == 5
    assert p.anios_cumplidos(date(2020, 12, 1), date(2026, 12, 1)) == 6


def test_vacaciones_descuenta_tomados_y_calcula_prima_del_30() -> None:
    r = p.calcular_vacaciones(date(2023, 1, 10), date(2026, 11, 24), 4, salario_diario=500.0)
    assert r.anios_servicio == 3
    assert r.dias_correspondientes == 16
    assert r.dias_disponibles == 12
    assert r.prima_vacacional_estimada == pytest.approx(12 * 500 * 0.30)


def test_vacaciones_nunca_negativas() -> None:
    r = p.calcular_vacaciones(date(2025, 1, 1), date(2026, 3, 1), 30, salario_diario=400.0)
    assert r.dias_disponibles == 0


def test_aguinaldo_anio_completo_es_20_dias_de_empresa_y_15_de_ley() -> None:
    r = p.calcular_aguinaldo(date(2015, 3, 3), date(2026, 11, 24), salario_diario=1000.0)
    assert r.dias_trabajados_en_anio == 365
    assert r.monto_empresa == pytest.approx(20_000.0)
    assert r.dias_minimo_ley == pytest.approx(15.0)
    assert r.monto_minimo_ley == pytest.approx(15_000.0)


def test_aguinaldo_proporcional_si_ingreso_en_el_anio() -> None:
    r = p.calcular_aguinaldo(date(2026, 7, 2), date(2026, 11, 24), salario_diario=365.0)
    assert r.dias_trabajados_en_anio == 183
    assert r.dias_aguinaldo_empresa == pytest.approx(20 * 183 / 365, abs=0.01)
