# ADR-0002: Google ADK como framework del agente

- **Estado:** aceptado
- **Fecha:** 2026-11-24

## Contexto

Necesitamos: definir tools a partir de funciones Python, mantener el contexto de la
conversación por sesión (RF-04), inyectar la identidad del usuario sin que el modelo la pueda
alterar, y obtener eventos de cada paso para la traza (RF-08). Todo con un modelo open-weight.

## Opciones consideradas

1. **Código propio** sobre LiteLLM: bucle "modelo → tool → modelo" escrito a mano.
2. **LangGraph:** grafo de estados explícito, muy flexible, más código de orquestación.
3. **Google ADK** (Agent Development Kit) con el conector `LiteLlm`.
4. **OpenAI Agents SDK / CrewAI.**

## Decisión

**Google ADK 2.x** con `LiteLlm(model=...)`.

Lo que nos da:
- **Tools desde funciones**: el docstring y los tipos se convierten en el esquema de la tool;
  el parámetro `tool_context` se inyecta solo y da acceso al estado de la sesión.
- **Sesiones** (`InMemorySessionService`, intercambiable por `DatabaseSessionService`): el
  historial por `session_id` y un **estado** donde el backend escribe `id_empleado_actual` y
  `rol_actual`. Las tools leen ese estado para autorizar; el modelo no lo puede escribir.
- **Plantillas de instrucción**: `{rol_actual}` en el prompt se rellena desde el estado.
- **Eventos tipados** (`get_function_calls`, `get_function_responses`, `usage_metadata`)
  que convertimos directamente en la traza y en métricas de tokens.
- Camino a multiagente (subagentes, `AgentTool`) sin reescribir si el alcance crece.

## Consecuencias

- ✅ Menos código de orquestación que propio o LangGraph; el foco queda en tools y seguridad.
- ✅ Modelo intercambiable por LiteLLM (Groq, Ollama, Gemini) cambiando un string.
- ⚠️ ADK está optimizado para Gemini; con otros modelos hay que usar el proveedor
  `ollama_chat` (no `ollama`) para evitar bucles de tool calls, como indica su documentación.
- ⚠️ Dependencia pesada (`google-adk` arrastra el SDK de GenAI y OpenTelemetry). Aceptable
  para un servicio; sería excesivo para una función serverless pequeña.
- ⚠️ El `Runner` y sus eventos cambian entre versiones mayores: fijamos `google-adk>=2.15,<3`
  y aislamos su uso en `app/agent/` (las pruebas usan un `Runner` simulado).
