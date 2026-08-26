# 07. Roadmap de Autonomía (JARVIS)

## Visión del Producto

Evolucionar a ADA de un asistente reactivo basado en prompts a un compañero proactivo con **autonomía controlada**:
1. Recibir eventos autorizados (archivos nuevos, alertas de transporte, eventos de calendario, webhook móvil).
2. Evaluar reglas y proponer o ejecutar acciones no destructivas.
3. Solicitar confirmación explícita para acciones sensibles.
4. Mantener trazabilidad completa y reversibilidad de cambios.


## Fases de Evolución

### Fase 1: Estabilización del Núcleo (Completada ✅)
- Motor multiagente local (Ollama / llama.cpp / Gemini / Groq).
- Persistencia en SQLite con WAL y cifrado Fernet en Bóveda.
- Integración de MCPs de archivos, fotos, transporte y búsqueda.

### Fase 2: Autonomía Controlada y Triggers (Activa 🟡)
- Daemon de triggers (`ada-autonomous`) monitoreando cron y carpetas.
- Notificaciones matutinas automáticas de Google Calendar vía Telegram.
- Detección y evaluación automática de nuevas fotografías en disco.

### Fase 3: Interfaz de Voz y Presencia (En Planificación ⏳)
- Speech-to-Text local con `faster-whisper`.
- Detección de presencia física / red local para contextualizar sugerencias.
- Síntesis de voz liviana (TTS local).

### Fase 4: Autonomía Completa Asistida (Futuro 🔮)
- Generación y ejecución de flujos de trabajo multi-paso con auto-corrección.
- Fine-tuning local de modelos pequeños para tool-calling especializado.
