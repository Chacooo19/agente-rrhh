"""Detección heurística de prompt injection en texto de usuario y en documentos.

No es la única defensa (ver docs/agentes/agente_rrhh.md, sección "Límites y salvaguardas"):
1. Este detector marca y neutraliza fragmentos sospechosos antes de que lleguen al modelo.
2. El system prompt trata todo resultado de tools como datos, nunca como instrucciones.
3. La autorización real vive en el código de las tools: aunque el modelo fuera engañado,
   un empleado no puede leer datos de otro.
"""

from __future__ import annotations

import re

_PATRONES: dict[str, re.Pattern[str]] = {
    "ignorar_instrucciones": re.compile(
        r"(ignora|olvida|omite|descarta|ignore|forget|disregard)\s+(todas?\s+|all\s+)?"
        r"(tus|las|los|your|the|previous|prior)?\s*(instrucciones|reglas|indicaciones|"
        r"instructions|rules|prompts?)",
        re.IGNORECASE,
    ),
    "cambio_de_rol": re.compile(
        r"(ahora\s+eres|act[úu]a\s+como|finge\s+(que\s+)?ser|you\s+are\s+now|act\s+as|"
        r"pretend\s+to\s+be|modo\s+(desarrollador|administrador|dios)|developer\s+mode)",
        re.IGNORECASE,
    ),
    "revelar_prompt": re.compile(
        r"(revela|muestra|imprime|repite|reveal|print|show)\s+(tu|tus|el|your|the)?\s*"
        r"(system\s*prompt|prompt\s+del\s+sistema|instrucciones\s+(del\s+sistema|internas|"
        r"ocultas)|initial\s+instructions)",
        re.IGNORECASE,
    ),
    "instruccion_para_ia": re.compile(
        r"(instrucci[óo]n|mensaje|nota)\s+(oculta\s+)?para\s+(el|la)\s+(asistente|ia|"
        r"modelo|agente)|\bto\s+the\s+(ai|assistant|model)\b",
        re.IGNORECASE,
    ),
    "tokens_de_control": re.compile(
        r"<\|?(system|im_start|im_end|endoftext)\|?>|\[/?INST\]|###\s*system", re.IGNORECASE
    ),
    "exfiltracion_masiva": re.compile(
        r"(todos|todas|all)\s+(los\s+|las\s+)?(empleados|salarios|expedientes|employees|"
        r"salaries)",
        re.IGNORECASE,
    ),
}

# Este patrón por sí solo no basta para marcar un texto (un usuario de RRHH puede pedir
# "todos los empleados de Finanzas"); solo cuenta si aparece junto con otro patrón.
_PATRONES_DEBILES = {"exfiltracion_masiva"}

_COMENTARIO_HTML = re.compile(r"<!--.*?-->", re.DOTALL)

TEXTO_NEUTRALIZADO = (
    "[Fragmento omitido: contenía instrucciones dirigidas a un asistente de IA y se descartó "
    "como posible prompt injection]"
)


def detectar_injection(texto: str) -> list[str]:
    """Devuelve los nombres de los patrones sospechosos encontrados (vacío si no hay)."""
    encontrados = [nombre for nombre, patron in _PATRONES.items() if patron.search(texto)]
    if set(encontrados) <= _PATRONES_DEBILES:
        return []
    return encontrados


def sanear_documento(texto: str) -> tuple[str, list[str]]:
    """Quita contenido oculto (comentarios HTML) y reporta patrones sospechosos.

    Devuelve el texto limpio y la lista de patrones detectados en el texto ORIGINAL,
    para poder registrar en la traza qué se eliminó.
    """
    patrones = detectar_injection(texto)
    ocultos = _COMENTARIO_HTML.findall(texto)
    if ocultos:
        patrones = sorted(set(patrones) | {"contenido_oculto_html"})
    limpio = _COMENTARIO_HTML.sub("", texto)
    return limpio, patrones
