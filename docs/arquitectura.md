# Arquitectura

## Componentes

```mermaid
flowchart LR
    U["Persona usuaria<br/>(empleado o RRHH)"] -->|navegador| UI["Interfaz web<br/>HTML + JS"]
    UI -->|"POST /api/login<br/>POST /api/chat (Bearer JWT)"| API["Backend FastAPI<br/>auth · validación · errores"]
    API -->|"identidad del token<br/>→ estado de sesión"| SVC["ServicioAgente<br/>sesiones ADK · traza · métricas"]
    SVC --> AG["Agente 'Alta'<br/>Google ADK (LlmAgent)<br/>prompt v1"]
    AG <-->|"LiteLLM"| LLM["gpt-oss-120b (respaldo: 20b)<br/>Groq (por defecto)<br/>u Ollama local"]
    AG --> T1["buscar_normativa"]
    AG --> T2["consultar_empleado"]
    AG --> T3["calcular_prestaciones"]
    AG --> T4["crear_ticket_rrhh"]
    AG --> T5["listar_tickets"]
    T1 --> RAG["Recuperador<br/>FastEmbed + índice NumPy<br/>umbral + neutralización"]
    RAG --> IDX[("Índice vectorial<br/>LFT + reglamento + política")]
    T2 & T3 & T4 & T5 --> DB[("SQLite<br/>empleados · usuarios · tickets")]
    T3 --> CALC["Cálculo determinista<br/>LFT art. 76, 80, 87"]
    SVC -->|"logs JSON por turno"| LOG["stdout"]

    subgraph Ingesta["Ingesta (en el build de Docker)"]
        PDF["LFT.pdf"] --> CH["Chunking por artículo<br/>+ saneamiento anti-injection"]
        MD["Documentos internos .md"] --> CH
        CH --> EMB["Embeddings<br/>multilingual-MiniLM"] --> IDX
    end
```

## Flujo de una consulta

```mermaid
sequenceDiagram
    autonumber
    participant N as Navegador
    participant A as FastAPI
    participant S as ServicioAgente
    participant G as Agente ADK
    participant M as Modelo (gpt-oss-120b)
    participant T as Tools
    N->>A: POST /api/chat {mensaje, session_id} + JWT
    A->>A: valida JWT → usuario, rol, id_empleado
    A->>S: conversar(...)
    S->>S: recupera o crea sesión ADK con {id_empleado_actual, rol_actual}
    S->>S: detector de injection en el mensaje (alerta en traza)
    S->>G: run_async(mensaje)
    G->>M: prompt + historial de la sesión + esquemas de tools
    M-->>G: llamada a buscar_normativa("días de vacaciones…")
    G->>T: buscar_normativa
    T-->>G: fragmentos citables (saneados) o encontrado=false
    M-->>G: llamada a calcular_prestaciones("", "vacaciones")
    G->>T: calcular_prestaciones (valida permisos con el estado de sesión)
    T-->>G: días, prima y fundamento
    G->>M: resultados de tools
    M-->>G: respuesta final con citas
    G-->>S: eventos (llamadas, resultados, texto, tokens)
    S-->>A: respuesta + traza + fuentes + alertas + latencia
    A-->>N: JSON → burbuja de chat + panel "¿Cómo llegó a la respuesta?"
```

## Decisiones clave (detalle en `docs/adr/`)

| Decisión | Elección | ADR |
|---|---|---|
| Modelo | gpt-oss-120b con respaldo gpt-oss-20b (open-weight, Apache 2.0) vía Groq; Ollama como alternativa local | [0001](adr/0001-modelo-open-source-sin-fine-tuning.md) |
| Framework | Google ADK con LiteLLM | [0002](adr/0002-framework-google-adk.md) |
| Arquitectura | Un solo agente con 5 tools; autorización en el código de las tools | [0003](adr/0003-agente-unico-con-autorizacion-en-tools.md) |
| Datos y RAG | Chunking por artículo, FastEmbed local, índice NumPy, SQLite | [0004](adr/0004-rag-y-almacenamiento.md) |
| Interfaz y API | FastAPI + página web estática con login por roles | [0005](adr/0005-interfaz-web-y-api.md) |
| Contenerización | Docker multi-etapa con índice precalculado + Compose | [0006](adr/0006-contenerizacion.md) |

## Defensa contra prompt injection (tres capas)

1. **Ingesta:** se eliminan los comentarios HTML ocultos y se marca todo fragmento cuyo texto
   visible contenga instrucciones para la IA (`app/guardrails.py`). Los fragmentos marcados
   llegan al modelo como `[Fragmento omitido…]`. Cada eliminación queda en la traza.
2. **Prompt:** el system prompt declara que todo resultado de tools es información, nunca
   instrucciones, y que el rol de la sesión no cambia por lo que diga el usuario.
3. **Código:** los permisos se validan dentro de cada tool con la identidad que el backend
   escribió en el estado de la sesión a partir del JWT. Aunque el modelo fuera engañado y
   llamara `consultar_empleado("E010")` en nombre de E005, la tool responde `no_autorizado`.

## Observabilidad

Cada turno escribe una línea JSON en stdout con: usuario, session_id, tools usadas, fuentes
citadas, alertas, latencia, tokens de entrada/salida, modelo y versión del prompt. Sirve para:

- medir costo real por consulta (tokens × precio) y latencia p50/p95;
- auditar quién consultó qué expediente (los accesos denegados se registran aparte);
- detectar intentos de injection (campo `alertas`);
- comparar versiones de prompt en producción.

La misma información se muestra al usuario en el panel de traza de la interfaz (RF-08).
