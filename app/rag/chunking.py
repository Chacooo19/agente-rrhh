"""Partición de documentos normativos en fragmentos (chunks) por artículo.

Estrategia: en textos legales la unidad natural de significado es el artículo, y es lo
que el usuario necesita citar. Por eso cortamos por artículo en lugar de por número fijo de
tokens. Si un artículo es muy largo (p. ej. el 132 de la LFT con decenas de fracciones),
se subdivide en ventanas con traslape, conservando el número de artículo en los metadatos.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any

MAX_CARACTERES = 1500
TRASLAPE = 200

# "Artículo 76.-", "Artículo 132 Bis.-", "Artículo 5o.-" en la LFT
_PATRON_ARTICULO_LFT = re.compile(
    r"^\s*Art[íi]culo\s+(\d+\s*[oº]?(?:\s*-?\s*(?:Bis|Ter|Quater|Quintus|[A-Z]))?)\s*\.\s*-",
    re.MULTILINE,
)
# "## Artículo 7. Aguinaldo" en los documentos internos en Markdown
_PATRON_ARTICULO_MD = re.compile(r"^##\s+Art[íi]culo\s+(\d+)\.\s*(.*)$", re.MULTILINE)

# Ruido de encabezados y pies de página del PDF de la Cámara de Diputados
_RUIDO_PDF = [
    re.compile(r"^\s*LEY FEDERAL DEL TRABAJO\s*$", re.MULTILINE),
    re.compile(r"^\s*C[ÁA]MARA DE DIPUTADOS DEL H\. CONGRESO DE LA UNI[ÓO]N\s*$", re.MULTILINE),
    re.compile(r"^\s*Secretar[íi]a General\s*$", re.MULTILINE),
    re.compile(r"^\s*Secretar[íi]a de Servicios Parlamentarios\s*$", re.MULTILINE),
    re.compile(r"^\s*[ÚU]ltima Reforma DOF.*$", re.MULTILINE),
    re.compile(r"^\s*\d+\s+de\s+\d+\s*$", re.MULTILINE),
]


@dataclass
class Fragmento:
    """Unidad mínima que se indexa y se cita."""

    id: str
    fuente: str  # "LFT" | "Reglamento interno" | ...
    articulo: str
    titulo: str
    texto: str
    documento: str
    sospechoso: bool = False
    patrones_sospechosos: list[str] = field(default_factory=list)

    def a_dict(self) -> dict[str, Any]:
        return asdict(self)


def limpiar_texto_pdf(texto: str) -> str:
    for patron in _RUIDO_PDF:
        texto = patron.sub("", texto)
    texto = re.sub(r"[ \t]+", " ", texto)
    return re.sub(r"\n{3,}", "\n\n", texto).strip()


def _normalizar_articulo(numero: str) -> str:
    numero = re.sub(r"\s+", " ", numero.replace("º", "o")).strip()
    numero = re.sub(r"(\d+)\s*o\b", r"\1", numero)  # "5o" -> "5"
    return numero.replace(" -", " ").replace("- ", " ").strip()


def _ventanas(texto: str) -> list[str]:
    if len(texto) <= MAX_CARACTERES:
        return [texto]
    partes: list[str] = []
    inicio = 0
    while inicio < len(texto):
        fin = min(inicio + MAX_CARACTERES, len(texto))
        # Cortar en un salto de línea o punto cercano para no partir frases
        if fin < len(texto):
            corte = max(texto.rfind("\n", inicio, fin), texto.rfind(". ", inicio, fin))
            if corte > inicio + MAX_CARACTERES // 2:
                fin = corte + 1
        partes.append(texto[inicio:fin].strip())
        if fin >= len(texto):
            break
        inicio = max(fin - TRASLAPE, inicio + 1)
    return partes


def _crear_fragmentos(
    fuente: str, documento: str, articulo: str, titulo: str, cuerpo: str
) -> list[Fragmento]:
    # Ids estables y en ASCII: "Política de bonos" -> "politica-de-bonos"
    sin_acentos = unicodedata.normalize("NFKD", fuente).encode("ascii", "ignore").decode()
    prefijo = re.sub(r"[^a-z0-9]+", "-", sin_acentos.lower()).strip("-")
    piezas = _ventanas(cuerpo.strip())
    return [
        Fragmento(
            id=f"{prefijo}-art{articulo.replace(' ', '')}" + (f"-p{i}" if len(piezas) > 1 else ""),
            fuente=fuente,
            articulo=articulo,
            titulo=titulo,
            texto=pieza,
            documento=documento,
        )
        for i, pieza in enumerate(piezas, start=1)
    ]


def quitar_transitorios(texto: str) -> str:
    """Corta el texto en los TRANSITORIOS que siguen al último artículo (1010).

    Los transitorios de cada reforma reinician la numeración ("Artículo 1o.", "Artículo 2o."…)
    y no son normas vigentes de uso cotidiano: solo meterían ruido en la búsqueda.
    """
    ultimo = re.search(r"Art[íi]culo\s+1010\s*\.", texto)
    if ultimo is None:
        return texto
    corte = re.search(r"^\s*TRANSITORIOS\s*$", texto[ultimo.end() :], re.MULTILINE)
    return texto if corte is None else texto[: ultimo.end() + corte.start()]


def fragmentar_lft(texto: str, documento: str = "LFT.pdf") -> list[Fragmento]:
    """Divide el texto completo de la LFT en fragmentos por artículo (sin transitorios)."""
    texto = limpiar_texto_pdf(quitar_transitorios(texto))
    coincidencias = list(_PATRON_ARTICULO_LFT.finditer(texto))
    fragmentos: list[Fragmento] = []
    vistos: dict[str, int] = {}
    for i, m in enumerate(coincidencias):
        fin = coincidencias[i + 1].start() if i + 1 < len(coincidencias) else len(texto)
        articulo = _normalizar_articulo(m.group(1))
        # Los artículos transitorios repiten numeración: les damos un sufijo único
        vistos[articulo] = vistos.get(articulo, 0) + 1
        clave = articulo if vistos[articulo] == 1 else f"{articulo}-T{vistos[articulo] - 1}"
        cuerpo = texto[m.start() : fin]
        fragmentos.extend(
            _crear_fragmentos("LFT", documento, clave, f"Artículo {articulo}", cuerpo)
        )
    return fragmentos


def fragmentar_markdown(texto: str, fuente: str, documento: str) -> list[Fragmento]:
    """Divide un documento interno en Markdown por sus encabezados '## Artículo N.'."""
    coincidencias = list(_PATRON_ARTICULO_MD.finditer(texto))
    fragmentos: list[Fragmento] = []
    for i, m in enumerate(coincidencias):
        fin = coincidencias[i + 1].start() if i + 1 < len(coincidencias) else len(texto)
        articulo, titulo = m.group(1), m.group(2).strip()
        cuerpo = texto[m.start() : fin]
        fragmentos.extend(_crear_fragmentos(fuente, documento, articulo, titulo, cuerpo))
    return fragmentos
