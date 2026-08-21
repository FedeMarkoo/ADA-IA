# Modelfiles Personalizados

La carpeta `models/modelfiles/` almacena los archivos de definición de modelos de Ollama (`Modelfile`), donde se definen la personalidad, parámetros de temperatura y reglas del sistema.

---

## 📄 Modelfiles Disponibles

### 1. `Modelfile.ada`
Modelfile principal para el asistente conversacional ADA:
- **Base**: `llama3.2:3b`
- **System Prompt**: Define la personalidad servicial, directa, concisa y experta en Python y fotografía.

### 2. `Modelfile.vision`
Modelfile para evaluación de imágenes y fotografía:
- **Base**: `llava:7b`
- **System Prompt**: Enfatiza el análisis de composición, paleta cromática, balance de blancos y grading estético.

---

## 🚀 Cómo Crear un Modelo en Ollama

```bash
# Crear el modelo personalizado en Ollama
ollama create ada -f models/modelfiles/Modelfile.ada
ollama create ada-vision -f models/modelfiles/Modelfile.vision
```
