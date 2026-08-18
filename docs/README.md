# ADA

Índice general de documentación de ADA. El contenido está separado por
responsabilidad: proyecto, skills y memoria.

## Por dónde empezar

- [Documentación del proyecto](project/README.md)
- [Skills](skills/README.md)
- [Memoria](memory/README.md)

## Separación de contenidos

- `docs/project/`: objetivos, arquitectura, funcionalidades e integración de
  ADA como producto.
- `docs/skills/`: contratos y uso de capacidades ejecutables individuales.
- `docs/memory/`: resúmenes generados para memoria y auditoría.

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
