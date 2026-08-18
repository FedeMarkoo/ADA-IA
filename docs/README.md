# ADA

Índice general de documentación de ADA. El contenido está separado por
 responsabilidad: proyecto y capabilities.

## Por dónde empezar

- [Documentación del proyecto](project/README.md)
- [Capabilities](capabilities/README.md)

## Separación de contenidos

- `docs/project/`: objetivos, arquitectura, funcionalidades e integración de
  ADA como producto.
- `docs/capabilities/`: contratos y uso de capacidades ejecutables individuales.

## Instalación rápida

```bash
cd /Users/home/Desktop/ADA
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python ada.py serve
```

La interfaz web queda disponible en `http://127.0.0.1:5005/`.

ADA usa Ollama como motor local actual. Los modelos configurados son
`llama3.2:3b` para conversación y `qwen2.5vl:3b` para visión.

## Principios

ADA debe ser local-first, multiagente, modular, observable, reversible y
cuidadosa con la privacidad y los recursos del equipo. La autonomía debe surgir
de eventos y reglas autorizadas, no de prompts ocultos ni acciones irreversibles.
