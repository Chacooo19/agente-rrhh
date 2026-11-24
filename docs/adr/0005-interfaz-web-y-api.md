# ADR-0005: Backend FastAPI y página web propia con login por roles

- **Estado:** aceptado
- **Fecha:** 2026-11-24

## Contexto

Usuarios finales: personas trabajadoras sin perfil técnico y personal de RRHH. Necesitan
iniciar sesión (los datos son confidenciales), chatear, ver de dónde salió cada respuesta y,
en el caso de RRHH, revisar los tickets escalados. También se requiere una API documentada.

## Opciones consideradas

1. **Streamlit / Gradio / Chainlit:** UI de chat en pocas líneas, pero el login por roles,
   el panel de traza a la medida y la bandeja de tickets se vuelven forzados; además mezclan
   UI y backend en un mismo proceso con su propio modelo de sesión.
2. **React/Next.js:** máxima flexibilidad, pero agrega toolchain de Node y un segundo
   contenedor; demasiado para 6 horas.
3. **FastAPI + HTML/CSS/JS sin framework**, servido por el mismo backend.
4. Solo la UI de desarrollo de ADK (`adk web`): no tiene login ni es para usuarios finales.

## Decisión

Opción 3.

- **API REST** (`/api/login`, `/api/chat`, `/api/tickets`, `/api/salud`) con contrato en
  Pydantic y documentación OpenAPI automática en `/docs`.
- **Autenticación JWT** (HS256, expira en 120 min) y contraseñas con **scrypt** de la
  librería estándar. El token define usuario, rol e id de empleado; el backend copia esa
  identidad al estado de la sesión del agente.
- **Página única** (`app/web/`) con login, chat, sugerencias por rol, estados de carga y
  error, panel "¿Cómo llegó a la respuesta?" (tools, fuentes, alertas, latencia, tokens) y
  pestaña de tickets solo para RRHH. Todo el texto se pinta con `textContent` (nunca
  `innerHTML`) para no abrir un XSS con lo que responda el modelo.

## Consecuencias

- ✅ Un solo proceso y un solo contenedor; la UI no necesita build.
- ✅ La misma API sirve para la UI, `curl` y futuras integraciones (Teams, Slack).
- ⚠️ Sin framework, la UI crece mal más allá de unas cuantas pantallas; con más tiempo se
  migraría a React y se agregaría streaming de respuestas (SSE).
- ⚠️ El token se guarda en `sessionStorage` (se borra al cerrar la pestaña). En producción se
  usaría cookie `HttpOnly` + SSO corporativo y bloqueo por intentos fallidos.
