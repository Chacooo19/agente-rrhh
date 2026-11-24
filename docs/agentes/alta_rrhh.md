# Ficha del agente: Alta (asistente de RRHH)

## Propósito y alcance

Resuelve las dudas recurrentes de las personas trabajadoras de Grupo Altavista (empresa
ficticia) sobre políticas y prestaciones, con respuestas fundamentadas en la Ley Federal del
Trabajo y el reglamento interno, y calcula sus prestaciones con sus propios datos.

**Sí hace**
- Responde preguntas de normativa citando fuente y artículo (vacaciones, aguinaldo, prima
  vacacional, permisos, home office, horas extra, retardos, bonos, maternidad/paternidad).
- Calcula días de vacaciones disponibles, prima vacacional y aguinaldo de la persona.
- Para el rol RRHH: consulta el expediente de cualquier empleado y lista tickets.
- Escala a RRHH creando un ticket con folio cuando no sabe o el caso es particular.

**No hace**
- Temas ajenos a RRHH (programación, recetas, política, inversiones…).
- Asesoría legal para litigar contra la empresa.
- Mostrar datos de una persona a otra (salvo rol RRHH).
- Modificar datos de nómina o aprobar vacaciones (solo informa y escala).

## Modelo y parámetros

| Parámetro | Valor | Por qué |
|---|---|---|
| Proveedor | Groq vía LiteLLM (alternativa: Ollama local) | Latencia baja y capa gratuita; mismo modelo en local para privacidad (ADR-0001) |
| Modelo | `openai/gpt-oss-20b` | Open-weight Apache 2.0, entrenado para uso agéntico y tool calling |
| Temperatura | 0.2 | Respuestas consistentes sobre normativa; poca variación entre ejecuciones |
| Máx. tokens de salida | 1500 | Las respuestas son breves; el margen cubre el razonamiento interno del modelo |
| Framework | Google ADK 2.x (`LlmAgent`) | Tools, sesiones y eventos para la traza (ADR-0002) |

## Prompt

- Archivo: [`prompts/agente_rrhh.v1.md`](../../prompts/agente_rrhh.v1.md)
- Versión: **v1** (`VERSION_PROMPT = "agente_rrhh.v1"` en `app/agent/agente.py`; viaja en la
  traza y en los logs de cada turno).
- Notas de diseño y cómo se prueba: [`prompts/README.md`](../../prompts/README.md)

## Tools

| Tool | Para qué | Entrada | Salida | Errores posibles |
|---|---|---|---|---|
| `buscar_normativa` | Recuperar artículos de la LFT y documentos internos | `consulta: str`, `fuente: "todas" \| "LFT" \| "Reglamento interno" \| "Política de bonos"` | `{ok, encontrado, fragmentos: [{id, fuente, articulo, titulo, texto, puntaje, neutralizado, alertas}]}` | `sin_sesion`, `rag_no_disponible`; `encontrado=false` si nada supera el umbral |
| `consultar_empleado` | Expediente: puesto, área, ingreso, antigüedad, salario diario, vacaciones tomadas | `id_empleado: str` (`""` = yo) | `{ok, empleado: {...}, fecha_referencia}` | `no_autorizado`, `no_encontrado`, `sin_sesion` |
| `calcular_prestaciones` | Vacaciones disponibles, prima vacacional (30%) y aguinaldo (20 días, proporcional) | `id_empleado: str`, `concepto: "vacaciones" \| "aguinaldo" \| "todas"` | `{ok, vacaciones: {...}, aguinaldo: {...}, fecha_referencia}` con `fundamento` | Los mismos de `consultar_empleado`; concepto inválido → `todas` |
| `crear_ticket_rrhh` | Escalar un caso a RRHH | `asunto: str`, `detalle: str`, `prioridad: "baja" \| "media" \| "alta"` | `{ok, folio, prioridad, plazo_respuesta}` | `datos_incompletos`, `sin_sesion`; prioridad inválida → `media` |
| `listar_tickets` | Bandeja de tickets (solo RRHH) | `estado: "abierto" \| "cerrado" \| "todos"` | `{ok, total, tickets: [...]}` | `no_autorizado`, `sin_sesion` |

Todas devuelven `{"ok": false, "error": <código>, "mensaje": <texto>}` ante un error, en vez
de lanzar excepciones, para que el modelo pueda explicarlo al usuario.

## Datos y memoria

- **Fuentes:** `data/raw/LFT.pdf` (pública), `data/docs/reglamento_interno.md` y
  `data/docs/politica_bonos_2026.md` (ficticios), `data/seed/empleados.csv` (sintético).
  Detalle en [`data/FUENTES.md`](../../data/FUENTES.md).
- **Indexación:** un fragmento por artículo (los largos se dividen con traslape), embeddings
  `paraphrase-multilingual-MiniLM-L12-v2` con FastEmbed, índice NumPy en `data/index/`
  (ADR-0004). Se construye con `python -m app.rag.ingest` o en el build de Docker.
- **Entre turnos:** ADK guarda el historial de mensajes y llamadas a tools por `session_id`
  (en memoria). El estado de la sesión contiene `id_empleado_actual` y `rol_actual`, que
  escribe el backend desde el JWT y el modelo no puede modificar. "Nueva conversación" en la
  interfaz crea otra sesión. No hay memoria de largo plazo entre sesiones.

## Flujo

1. El backend valida el JWT y crea o recupera la sesión ADK del usuario.
2. Se revisa el mensaje con el detector de injection (solo alerta; no bloquea).
3. El agente sigue la receta del prompt:
   1. `buscar_normativa` para cualquier regla o derecho;
   2. `consultar_empleado` / `calcular_prestaciones` si la pregunta es sobre la persona;
   3. si no hay fundamento o el caso es particular, ofrece `crear_ticket_rrhh` y lo crea al
      confirmar el usuario.
4. Responde en español, breve, con cita `(Fuente, art. N)` y la fecha de referencia de los
   cálculos.
5. El servicio arma la traza (tools, argumentos, resultados recortados), fuentes, alertas,
   latencia y tokens, y la devuelve a la interfaz y a los logs.

## Límites y salvaguardas

- **Fuera de alcance:** el prompt define qué atiende; para todo lo demás responde en una
  frase que solo atiende dudas de RRHH.
- **No sabe:** si `buscar_normativa` devuelve `encontrado=false` (nada supera el umbral de
  similitud), responde "No encuentro eso en la normativa disponible" y ofrece un ticket.
- **Prompt injection:** tres capas (ingesta, prompt, autorización en código). Ver
  [`docs/arquitectura.md`](../arquitectura.md#defensa-contra-prompt-injection-tres-capas).
- **Falla de una tool:** devuelve error estructurado; el agente lo explica y ofrece escalar.
  Si el índice no cargó, `buscar_normativa` responde `rag_no_disponible` y `/api/salud` lo
  reporta.
- **Falla del modelo** (sin API key, límite de uso, red, >90 s): la API responde 503 con un
  mensaje claro y la interfaz lo muestra sin perder la conversación.
- **Entrada:** mensajes de máximo 2,000 caracteres.

## Ejemplos

Con `FECHA_REFERENCIA=2026-11-24` (valores de `.env.example`):

| Usuario | Entrada | Salida esperada |
|---|---|---|
| `e005` (empleado, ingreso 2021-07-21) | "¿Cuántos días de vacaciones me quedan?" | 20 días disponibles (5 años de servicio, 0 tomados), prima vacacional estimada de $3,177.12. Cita LFT art. 76 y Reglamento art. 5 y 6. |
| `e005` | "¿Cuál es el salario de E012?" | Se niega: la información es confidencial (Reglamento art. 14). La traza muestra `consultar_empleado` → `no_autorizado` si el modelo lo intentó. |
| `e001` (RRHH) | "¿Qué antigüedad tiene E012 y cuántas vacaciones le quedan?" | 22 años de servicio, 28 días por ley, 7 tomados, 21 disponibles. |
| cualquiera | "¿Cómo hago un for en Python?" | Indica que solo atiende dudas de RRHH. |
