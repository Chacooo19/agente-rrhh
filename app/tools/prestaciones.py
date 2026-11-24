"""Cálculo determinista de prestaciones según la LFT y el reglamento interno ficticio.

Los números los calcula el código, no el modelo: los LLM se equivocan en aritmética y aquí
un error es dinero. El modelo solo explica el resultado.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# Reglamento interno de Grupo Altavista (data/docs/reglamento_interno.md)
DIAS_AGUINALDO_EMPRESA = 20  # Art. 7 reglamento (LFT art. 87: mínimo 15)
PRIMA_VACACIONAL_EMPRESA = 0.30  # Art. 6 reglamento (LFT art. 80: mínimo 25%)
DIAS_AGUINALDO_LEY = 15
PRIMA_VACACIONAL_LEY = 0.25


def anios_cumplidos(ingreso: date, hoy: date) -> int:
    """Años completos de servicio a la fecha `hoy`."""
    anios = hoy.year - ingreso.year
    if (hoy.month, hoy.day) < (ingreso.month, ingreso.day):
        anios -= 1
    return max(anios, 0)


def dias_vacaciones_por_ley(anios: int) -> int:
    """Días de vacaciones según el art. 76 LFT (reforma "vacaciones dignas", DOF 27/12/2022).

    1 año: 12 días; +2 por año hasta 20 días al quinto año; a partir del sexto año,
    +2 días por cada 5 años de servicio (6-10: 22, 11-15: 24, 16-20: 26, ...).
    """
    if anios < 1:
        return 0
    if anios <= 5:
        return 12 + 2 * (anios - 1)
    return 20 + 2 * ((anios - 6) // 5 + 1)


@dataclass(frozen=True)
class ResultadoVacaciones:
    anios_servicio: int
    dias_correspondientes: int
    dias_tomados: int
    dias_disponibles: int
    prima_vacacional_estimada: float
    fundamento: str


@dataclass(frozen=True)
class ResultadoAguinaldo:
    dias_trabajados_en_anio: int
    dias_aguinaldo_empresa: float
    monto_empresa: float
    dias_minimo_ley: float
    monto_minimo_ley: float
    fundamento: str


def calcular_vacaciones(
    ingreso: date, hoy: date, dias_tomados: int, salario_diario: float
) -> ResultadoVacaciones:
    anios = anios_cumplidos(ingreso, hoy)
    dias = dias_vacaciones_por_ley(anios)
    disponibles = max(dias - dias_tomados, 0)
    prima = round(disponibles * salario_diario * PRIMA_VACACIONAL_EMPRESA, 2)
    return ResultadoVacaciones(
        anios_servicio=anios,
        dias_correspondientes=dias,
        dias_tomados=dias_tomados,
        dias_disponibles=disponibles,
        prima_vacacional_estimada=prima,
        fundamento=(
            "LFT art. 76 (días por antigüedad) y art. 80 (prima mínima 25%); "
            "Reglamento interno arts. 5 y 6 (prima del 30%)."
        ),
    )


def calcular_aguinaldo(ingreso: date, hoy: date, salario_diario: float) -> ResultadoAguinaldo:
    """Aguinaldo del año calendario de `hoy`, proporcional si ingresó durante ese año."""
    inicio_anio = date(hoy.year, 1, 1)
    fin_anio = date(hoy.year, 12, 31)
    desde = max(ingreso, inicio_anio)
    dias_anio = (fin_anio - inicio_anio).days + 1
    trabajados = max((fin_anio - desde).days + 1, 0) if ingreso <= fin_anio else 0
    proporcion = trabajados / dias_anio
    dias_empresa = round(DIAS_AGUINALDO_EMPRESA * proporcion, 2)
    return ResultadoAguinaldo(
        dias_trabajados_en_anio=trabajados,
        dias_aguinaldo_empresa=dias_empresa,
        monto_empresa=round(dias_empresa * salario_diario, 2),
        dias_minimo_ley=round(DIAS_AGUINALDO_LEY * proporcion, 2),
        monto_minimo_ley=round(DIAS_AGUINALDO_LEY * proporcion * salario_diario, 2),
        fundamento=(
            "LFT art. 87 (mínimo 15 días, proporcional si no se completó el año); "
            "Reglamento interno art. 7 (20 días)."
        ),
    )
