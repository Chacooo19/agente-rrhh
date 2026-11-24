"""Base de datos SQLite: empleados (sintéticos), usuarios del portal y tickets a RRHH.

SQLite basta para la demo (un archivo, cero servicios extra) y se cambia por Postgres
sin tocar las tools porque todo el acceso pasa por este módulo. Ver ADR-0004.
"""

from __future__ import annotations

import csv
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from app.auth.security import hashear_password

ESQUEMA = """
CREATE TABLE IF NOT EXISTS empleados (
    id_empleado TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    area TEXT NOT NULL,
    puesto TEXT NOT NULL,
    fecha_ingreso TEXT NOT NULL,
    salario_diario REAL NOT NULL,
    dias_vacaciones_tomados INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS usuarios (
    usuario TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    rol TEXT NOT NULL CHECK (rol IN ('empleado', 'rrhh')),
    id_empleado TEXT NOT NULL REFERENCES empleados(id_empleado)
);
CREATE TABLE IF NOT EXISTS tickets (
    folio INTEGER PRIMARY KEY AUTOINCREMENT,
    id_empleado TEXT NOT NULL REFERENCES empleados(id_empleado),
    asunto TEXT NOT NULL,
    detalle TEXT NOT NULL,
    prioridad TEXT NOT NULL CHECK (prioridad IN ('baja', 'media', 'alta')),
    estado TEXT NOT NULL DEFAULT 'abierto' CHECK (estado IN ('abierto', 'cerrado')),
    creado_en TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class Empleado:
    id_empleado: str
    nombre: str
    area: str
    puesto: str
    fecha_ingreso: date
    salario_diario: float
    dias_vacaciones_tomados: int


@dataclass(frozen=True)
class Usuario:
    usuario: str
    password_hash: str
    rol: str
    id_empleado: str


@dataclass(frozen=True)
class Ticket:
    folio: int
    id_empleado: str
    asunto: str
    detalle: str
    prioridad: str
    estado: str
    creado_en: str


class BaseDatos:
    def __init__(self, ruta: Path) -> None:
        self.ruta = ruta

    @contextmanager
    def conexion(self) -> Iterator[sqlite3.Connection]:
        con = sqlite3.connect(self.ruta)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def inicializar(self, csv_empleados: Path, password_demo: str) -> None:
        """Crea el esquema y carga los datos de demostración si la base está vacía."""
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        with self.conexion() as con:
            con.executescript(ESQUEMA)
            if con.execute("SELECT COUNT(*) FROM empleados").fetchone()[0]:
                return
            with csv_empleados.open(encoding="utf-8") as f:
                filas = list(csv.DictReader(f))
            con.executemany(
                "INSERT INTO empleados VALUES (:id_empleado, :nombre, :area, :puesto, "
                ":fecha_ingreso, :salario_diario, :dias_vacaciones_tomados)",
                filas,
            )
            # Una cuenta por empleado: usuario = id en minúsculas (e001, e002...).
            # Quien pertenece al área de RRHH recibe el rol 'rrhh'.
            hash_demo = hashear_password(password_demo)
            con.executemany(
                "INSERT INTO usuarios VALUES (?, ?, ?, ?)",
                [
                    (
                        f["id_empleado"].lower(),
                        hash_demo,
                        "rrhh" if f["area"] == "Recursos Humanos" else "empleado",
                        f["id_empleado"],
                    )
                    for f in filas
                ],
            )

    # --- Empleados -----------------------------------------------------------------------
    def obtener_empleado(self, id_empleado: str) -> Empleado | None:
        with self.conexion() as con:
            fila = con.execute(
                "SELECT * FROM empleados WHERE id_empleado = ?", (id_empleado.upper(),)
            ).fetchone()
        if fila is None:
            return None
        datos = dict(fila)
        datos["fecha_ingreso"] = date.fromisoformat(datos["fecha_ingreso"])
        return Empleado(**datos)

    def buscar_empleados(self, texto: str) -> list[Empleado]:
        patron = f"%{texto.strip()}%"
        with self.conexion() as con:
            filas = con.execute(
                "SELECT id_empleado FROM empleados WHERE nombre LIKE ? OR area LIKE ? "
                "OR id_empleado LIKE ? ORDER BY id_empleado LIMIT 20",
                (patron, patron, patron),
            ).fetchall()
        return [e for f in filas if (e := self.obtener_empleado(f[0])) is not None]

    # --- Usuarios ------------------------------------------------------------------------
    def obtener_usuario(self, usuario: str) -> Usuario | None:
        with self.conexion() as con:
            fila = con.execute(
                "SELECT * FROM usuarios WHERE usuario = ?", (usuario.lower().strip(),)
            ).fetchone()
        return Usuario(**dict(fila)) if fila else None

    # --- Tickets -------------------------------------------------------------------------
    def crear_ticket(self, id_empleado: str, asunto: str, detalle: str, prioridad: str) -> Ticket:
        creado = datetime.now().isoformat(timespec="seconds")
        with self.conexion() as con:
            cursor = con.execute(
                "INSERT INTO tickets (id_empleado, asunto, detalle, prioridad, creado_en) "
                "VALUES (?, ?, ?, ?, ?)",
                (id_empleado, asunto, detalle, prioridad, creado),
            )
            folio = int(cursor.lastrowid or 0)
        return Ticket(folio, id_empleado, asunto, detalle, prioridad, "abierto", creado)

    def listar_tickets(self, estado: str | None = None) -> list[Ticket]:
        consulta = "SELECT * FROM tickets"
        parametros: tuple[str, ...] = ()
        if estado:
            consulta += " WHERE estado = ?"
            parametros = (estado,)
        with self.conexion() as con:
            filas = con.execute(consulta + " ORDER BY folio DESC", parametros).fetchall()
        return [Ticket(**dict(f)) for f in filas]
