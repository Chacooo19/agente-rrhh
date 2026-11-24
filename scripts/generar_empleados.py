"""Genera la plantilla sintética de empleados de la empresa ficticia "Grupo Altavista".

Todos los nombres se forman combinando listas genéricas al azar (semilla fija): no
corresponden a personas reales. Uso:

    python scripts/generar_empleados.py  # escribe data/seed/empleados.csv
"""

from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

SEMILLA = 2026
SALIDA = Path(__file__).resolve().parent.parent / "data" / "seed" / "empleados.csv"

NOMBRES = [
    "Ana",
    "Luis",
    "María",
    "Jorge",
    "Sofía",
    "Diego",
    "Valeria",
    "Carlos",
    "Fernanda",
    "Miguel",
    "Paola",
    "Ricardo",
    "Daniela",
    "Andrés",
    "Lucía",
    "Héctor",
    "Regina",
    "Raúl",
    "Camila",
    "Tomás",
]
APELLIDOS = [
    "Ramírez",
    "Torres",
    "Herrera",
    "Castillo",
    "Vargas",
    "Mendoza",
    "Ortega",
    "Rojas",
    "Navarro",
    "Delgado",
    "Cruz",
    "Morales",
    "Ibarra",
    "Salinas",
    "Acosta",
    "Fuentes",
]
PUESTOS = {
    "Recursos Humanos": [("Gerente de RRHH", 1450.0), ("Analista de nómina", 820.0)],
    "Operaciones": [
        ("Supervisor de almacén", 760.0),
        ("Auxiliar de almacén", 420.0),
        ("Montacarguista", 480.0),
    ],
    "Ventas": [("Ejecutivo de ventas", 650.0), ("Gerente comercial", 1600.0)],
    "Tecnología": [("Desarrollador", 1100.0), ("Soporte técnico", 560.0)],
    "Finanzas": [("Contador", 950.0), ("Auxiliar contable", 520.0)],
}


def generar(n: int = 24) -> list[dict[str, str]]:
    rng = random.Random(SEMILLA)
    filas: list[dict[str, str]] = []
    areas = list(PUESTOS)
    # Los dos primeros siempre son de RRHH para tener cuentas con ese rol
    otras_areas = [a for a in areas if a != "Recursos Humanos"]
    plan = ["Recursos Humanos", "Recursos Humanos"] + [
        rng.choice(otras_areas) for _ in range(n - 2)
    ]
    usados: set[str] = set()
    for i, area in enumerate(plan, start=1):
        while True:
            nombre = f"{rng.choice(NOMBRES)} {rng.choice(APELLIDOS)} {rng.choice(APELLIDOS)}"
            if nombre not in usados:
                usados.add(nombre)
                break
        puesto, salario_base = PUESTOS[area][0 if i == 1 else rng.randrange(len(PUESTOS[area]))]
        if i == 2:
            puesto, salario_base = PUESTOS["Recursos Humanos"][1]
        # Antigüedades variadas: de 3 meses a 22 años antes de 2026-11-01
        dias_atras = rng.randint(90, 22 * 365)
        ingreso = date(2026, 11, 1) - timedelta(days=dias_atras)
        salario = round(salario_base * rng.uniform(0.95, 1.15), 2)
        # Con menos de un año aún no se generan vacaciones (art. 76 LFT)
        tomados = 0 if dias_atras < 365 else rng.randint(0, 8)
        filas.append(
            {
                "id_empleado": f"E{i:03d}",
                "nombre": nombre,
                "area": area,
                "puesto": puesto,
                "fecha_ingreso": ingreso.isoformat(),
                "salario_diario": f"{salario:.2f}",
                "dias_vacaciones_tomados": str(tomados),
            }
        )
    return filas


def main() -> None:
    filas = generar()
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    with SALIDA.open("w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=list(filas[0]))
        escritor.writeheader()
        escritor.writerows(filas)
    print(f"{len(filas)} empleados escritos en {SALIDA}")


if __name__ == "__main__":
    main()
