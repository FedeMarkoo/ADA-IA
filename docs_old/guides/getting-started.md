# Guía de Inicio Rápido e Instalación

Esta guía te ayudará a instalar y levantar ADA-IA desde cero en tu máquina local.


## Requisitos previos

- **Python 3.10+** (Recomendado: Python 3.11, 3.12 o 3.14).
- **Ollama**: Descargá e instalá Ollama desde [ollama.com](https://ollama.com).
- **Git**


## Instalación en 3 pasos

### 1. Clonar e Inicializar Entorno Virtual
```bash
git clone https://github.com/tu-usuario/ADA-IA.git
cd ADA-IA

python3 -m venv .venv
source .venv/bin/activate
```

### 2. Instalar Dependencias en Modo Editable
```bash
pip install -e .
```

### 3. Descargar Modelo Base en Ollama
```bash
ollama pull llama3.2:3b
```


## Iniciar el gestor web

```bash
python -m ada.interfaces.web.server
```
Abrí tu navegador en **[http://127.0.0.1:5005](http://127.0.0.1:5005)** para acceder al panel de control interactivo.

Al abrirlo, verificá que el estado general sea saludable. La guía completa de cada pantalla está en [Guía de uso del dashboard](../user-guide.md).

![Resumen del dashboard](../screenshots/assets-overview.png)
