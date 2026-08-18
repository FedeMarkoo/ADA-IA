# ADA

Documentación principal del asistente local y autónomo.

## Por dónde empezar

- [Objetivo y roadmap](roadmap.md)
- [Arquitectura](architecture/overview.md)
- [Análisis de fotos](features/photo-analysis.md)
- [Compras y recetas](features/shopping-and-recipes.md)
- [XMP y ráfagas](features/xmp-and-bursts.md)
- [Telegram y Ollama](integrations/telegram-and-ollama.md)
- [Operación y recursos](operations.md)
- [Skills](skills/README.md)
- [Memoria](memory/README.md)

## Instalación rápida

```bash
cd /Users/home/Desktop/ADA
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python ui_server.py
```

La interfaz web queda disponible en `http://127.0.0.1:5005/`.

ADA usa Ollama como motor local actual. Los modelos configurados son
`llama3.2:3b` para conversación y `qwen2.5vl:3b` para visión.

## Principios

ADA debe ser local-first, multiagente, modular, observable, reversible y
cuidadosa con la privacidad y los recursos del equipo. La autonomía debe surgir
de eventos y reglas autorizadas, no de prompts ocultos ni acciones irreversibles.
