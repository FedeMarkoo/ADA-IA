# ADA - Modelos de Ollama & Benchmarks

Esta carpeta centraliza la configuración declarativa, Modelfiles y registros de rendimiento de los modelos LLM y visión soportados por ADA.

---

## 📁 Estructura

```text
models/
├── catalog.json              # 📋 Catálogo de modelos, tiers de hardware y roles asignados
├── benchmarks.json           # ⚡ Registro histórico de velocidad (tokens/seg) y latencia
├── modelfiles/               # 🛠️ Modelfiles personalizados para compilar modelos en Ollama
│   ├── Modelfile.ada         # Modelo base conversacional
│   ├── Modelfile.vision      # Modelo especializado en análisis visual
│   └── Modelfile.router      # Modelo rápido de clasificación
└── README.md
```

---

## 🚀 Cómo Descargar un Modelo con Ollama

Podés descargar modelos desde la interfaz gráfica de **ADA Hub (Ollama Hub)** o desde terminal:

```bash
ollama pull llama3.2:3b
ollama pull qwen2.5vl:3b
```

---

## 🛠️ Cómo Compilar un Modelo Personalizado

```bash
ollama create ada-chat -f models/modelfiles/Modelfile.ada
```
