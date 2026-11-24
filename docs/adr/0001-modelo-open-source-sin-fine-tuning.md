# ADR-0001: Modelo open-weight (gpt-oss-20b) sin fine-tuning, servido por Groq u Ollama

- **Estado:** aceptado, revisado el mismo día tras pruebas (ver al final)
- **Fecha:** 2026-11-24

## Contexto

El agente necesita: llamar herramientas de forma confiable (5 tools), responder en español,
seguir reglas estrictas de "no inventar" y "citar fuentes", y correr en la máquina del
evaluador con el mínimo de fricción. Restricciones: 6 horas de desarrollo, presupuesto cero,
datos laborales (sensibles) y un evaluador que levantará el proyecto con su propia API key.

## Opciones consideradas

1. **Modelo comercial (Gemini, GPT, Claude).** Mejor calidad de tool calling. Pero es de
   pago o con capa gratuita limitada, y los datos salen a un tercero sin opción local.
2. **Modelo open-weight local con Ollama dentro de Docker** (p. ej. qwen3:8b, gpt-oss:20b).
   Privacidad total y costo cero, pero obliga al evaluador a descargar varios GB y, sin GPU,
   la latencia por turno con varias llamadas a tools es de decenas de segundos. Riesgo alto
   de que "no arranque a la primera".
3. **Modelo open-weight servido por un proveedor (Groq) y configurable a Ollama.** Mismos
   pesos abiertos, latencia baja, capa gratuita sin tarjeta y la opción de moverlo a local
   cambiando una variable.
4. **Fine-tuning** de un modelo pequeño con preguntas de RRHH.

## Decisión

Opción 3 con **`openai/gpt-oss-20b`** (Apache 2.0) en Groq por defecto
(`LLM_MODEL=groq/openai/gpt-oss-20b`) y `ollama_chat/gpt-oss:20b` como alternativa local.

**Sin fine-tuning.** El conocimiento que necesita el agente (ley y reglamento) cambia con
cada reforma o política nueva; con RAG basta reindexar un documento, mientras que con
fine-tuning habría que reentrenar, y el modelo no podría citar de dónde sale cada respuesta
(RF-08) ni distinguir cuándo no sabe (RF-05). Además, no cabe en 6 horas con evaluación.

Por qué gpt-oss-20b y no Qwen3/Llama: es open-weight con licencia permisiva, está entrenado
para uso agéntico, tiene parser de tool calls dedicado en los principales runtimes (Ollama,
vLLM, llama.cpp, SGLang) y en Groq es el reemplazo recomendado tras el retiro de
`qwen3-32b` y `llama-3.1-8b-instant`. `gpt-oss-120b` queda como opción si se necesita más
calidad (mismo código, otra variable).

Parámetros: `temperature=0.2` (respuestas consistentes, poco creativas: es normativa) y
`max_output_tokens=1024` y `reasoning_effort=low` (respuestas cortas; menos tokens de
razonamiento). Ante un 429, LiteLLM reintenta con espera exponencial y después usa
`gpt-oss-120b` como respaldo: en Groq los límites son por modelo.

## Consecuencias

- ✅ Costo ≈ USD 0.001 por consulta en tarifa de pago (ver README) y 0 en la capa gratuita.
- ✅ Latencia de pocos segundos por turno, apta para una demo en vivo.
- ✅ Portabilidad: mismo modelo en la nube o 100% local (privacidad) sin tocar código.
- ⚠️ Con Groq, los textos de la conversación salen a un tercero. Para producción con datos
  reales se usaría la opción Ollama/vLLM on-premise.
- ⚠️ Un modelo de 20B se equivoca más que uno frontera al elegir tools. Se mitiga con un
  prompt de receta numerada, tools con docstrings claros, errores estructurados y cálculos
  deterministas en código.
- ⚠️ La capa gratuita de Groq limita gpt-oss-20b a 8K tokens por minuto y 200K por día, lo
  que alcanza para pocos turnos seguidos. Si aun con reintentos y respaldo se agota, la API
  devuelve un 503 con un mensaje claro. Para uso continuo: plan Developer de Groq u Ollama.

## Revisión (2026-11-24, tras pruebas con el modelo real)

**Qué pasó:** con `gpt-oss-20b`, ante el seguimiento "¿y si fuera solo lo que pide la ley?",
el modelo respondió con un salario inventado ("suponiendo un salario anual de $158,000") en
lugar del campo `monto_minimo_ley` que la tool ya había devuelto. Además, la capa gratuita
(8K tokens por minuto por modelo) se agotaba desde la segunda pregunta.

**Cambio:**
- Modelo principal: **`gpt-oss-120b`** (mismo licenciamiento open-weight, mejor apego a
  instrucciones). `gpt-oss-20b` queda como **respaldo** automático ante un 429; como Groq
  limita por modelo, tener dos duplica el margen.
- Prompt v2: los números se copian de las tools, nunca se suponen (ver `prompts/README.md`).
- Menos tokens por llamada: top-k 3, fragmentos recortados y `reasoning_effort=low`.

**Consecuencia:** el costo sube a ≈ USD 0.002 por consulta en tarifa de pago (sigue en USD 0
en la capa gratuita). En local con Ollama se usa el 20b, porque el 120b necesita ~65 GB de memoria.
