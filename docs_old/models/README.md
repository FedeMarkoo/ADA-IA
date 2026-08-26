# Modelos de Lenguaje & Visión (Ollama)

ADA utiliza **Ollama** como motor principal de inferencia local, permitiendo asignar modelos especializados a roles específicos según los recursos de hardware disponibles.


## Asignación de roles por tarea

Los roles se configuran en `models/catalog.json` y se gestionan dinámicamente desde el Dashboard:

| Rol | Modelo Recomendado | Requisitos Mínimos | Propósito |
| :--- | :--- | :--- | :--- |
| **`general`** (Chat Principal) | `llama3.2:3b` / `llama3.1:8b` | 4 GB RAM | Conversación general, razonamiento y planificación |
| **`coding`** (Desarrollo) | `qwen2.5-coder:7b` | 8 GB RAM / 6 GB VRAM | Generación, refactorización y análisis de código |
| **`vision`** (Fotografía & OCR) | `llava:7b` / `llama3.2-vision` | 8 GB RAM / 6 GB VRAM | Evaluación estética, análisis de composición y OCR |
| **`router`** (Clasificación Rápida)| `llama3.2:1b` / `qwen2.5:0.5b` | 2 GB RAM | Clasificación instantánea de intenciones (<50ms) |


## Benchmarking de velocidad

El sistema mide y persiste la velocidad de generación (tokens por segundo) en `models/benchmarks.json`.
Podés lanzar benchmarks en cualquier momento desde la pestaña **Modelos & Roles** del Dashboard o mediante la API:

```bash
curl -X POST http://127.0.0.1:5005/api/models/benchmark \
  -H "Content-Type: application/json" \
  -d '{"model": "llama3.2:3b", "prompt_key": "general"}'
```
