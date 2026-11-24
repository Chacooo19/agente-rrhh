# ADR-0003: Un solo agente con 5 tools y autorización dentro de las tools

- **Estado:** aceptado
- **Fecha:** 2026-11-24

## Contexto

El problema tiene tres tipos de trabajo: buscar normativa, consultar/calcular datos de una
persona y escalar a RRHH. Hay dos roles (empleado y RRHH) con permisos distintos sobre datos
confidenciales (salarios). Debe resistir prompt injection (RF-06).

## Opciones consideradas

1. **Agente único con tools.** Un LLM decide qué tool usar en cada turno.
2. **Orquestador + subagentes** (uno de normativa, uno de prestaciones, uno de tickets).
3. **Pipeline fijo** (siempre: clasificar → recuperar → calcular → redactar) sin decisión
   del modelo.

Y para los permisos:

a. Restringir en el prompt ("si eres empleado, no consultes a otros").
b. Validar en el código de cada tool con la identidad del token.

## Decisión

**Opción 1 + b.** Un agente ("Alta") con `buscar_normativa`, `consultar_empleado`,
`calcular_prestaciones`, `crear_ticket_rrhh` y `listar_tickets`.

- Cinco tools caben bien en el contexto de un modelo de 20B; dividir en subagentes agregaría
  una llamada extra al modelo por turno (más latencia y costo) y más puntos de falla en la
  delegación, sin mejorar la calidad para este alcance.
- Un pipeline fijo no maneja bien preguntas mixtas ("¿cuántas vacaciones me quedan y cómo
  las pido?") ni el seguimiento conversacional.
- La autorización en el prompt **no es seguridad**: un injection puede convencer al modelo.
  Por eso cada tool obtiene `id_empleado` y `rol` del estado de la sesión (escrito por el
  backend desde el JWT) y responde `no_autorizado` si no corresponde, sin importar lo que el
  modelo pida.
- Los números (días, montos) los calcula `calcular_prestaciones` en código.

## Consecuencias

- ✅ Arquitectura simple de explicar, probar (pruebas unitarias de permisos sin LLM) y operar.
- ✅ La defensa más fuerte contra injection no depende del modelo.
- ⚠️ Toda la lógica de decisión vive en un prompt: si crece el número de tools (>10) o de
  dominios (nómina, reclutamiento), conviene pasar a orquestador + subagentes por dominio
  (ADK lo soporta con `sub_agents`).
- ⚠️ El agente puede elegir mal una tool; se mitiga con docstrings explícitos y la receta
  numerada del prompt, y la traza deja ver cuándo pasa.
