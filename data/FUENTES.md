# Fuentes de datos

Ningún archivo de esta carpeta contiene datos personales reales ni información confidencial
de alguna empresa.

| Archivo | Qué es | Origen | Licencia / uso |
|---|---|---|---|
| `raw/LFT.pdf` | Ley Federal del Trabajo, texto vigente | Cámara de Diputados, H. Congreso de la Unión: https://www.diputados.gob.mx/LeyesBiblio/pdf/LFT.pdf (descargado el 24/11/2026) | Documento público. Los textos legislativos no son objeto de protección de derechos de autor (Ley Federal del Derecho de Autor, art. 14, fr. VIII). |
| `docs/reglamento_interno.md` | Reglamento interior de trabajo de la empresa ficticia "Grupo Altavista" | Redactado para esta prueba; sus prestaciones se basan en la LFT y algunas la mejoran a propósito (aguinaldo de 20 días, prima vacacional del 30%, paternidad de 10 días) para que el agente tenga que distinguir "lo que pide la ley" de "lo que da la empresa". | Ficticio |
| `docs/politica_bonos_2026.md` | Política de bonos ficticia **con una instrucción maliciosa escondida** en un comentario HTML | Redactado para demostrar la defensa contra prompt injection indirecto (RF-06) | Ficticio |
| `seed/empleados.csv` | 24 empleados sintéticos (nombre, área, puesto, fecha de ingreso, salario diario, vacaciones tomadas) | Generado con `scripts/generar_empleados.py` (semilla fija 2026). Los nombres combinan listas genéricas al azar. | Sintético |

## Por qué estos datos

- El problema real es que RRHH responde a mano las mismas preguntas (vacaciones, aguinaldo,
  permisos). Las respuestas correctas dependen de **dos fuentes** (la ley y la política
  interna) y de **datos de la persona** (antigüedad, salario, días tomados). Por eso el
  agente combina RAG sobre documentos con consultas a una base de datos y cálculos.
- La LFT es pública, extensa (~1,000 artículos) y redactada en lenguaje jurídico: es un buen
  caso para evaluar recuperación por artículo y citas.
- Los empleados son sintéticos para cumplir con "no uses datos personales reales".
