# Dashboard Gestor Web (ADA Hub)

El Dashboard de ADA Hub (`dashboard/`) es una interfaz moderna desarrollada en **React 19 SPA**, diseñada para monitorear la salud del sistema, controlar servidores MCP, gestionar modelos de Ollama y administrar el bot de Telegram.

---

## 🎨 Características Visuales y de UX

- **Dark Theme Nativo**: Sistema de diseño con tokens de color HSL y tipografías *Inter*, *Outfit* y *JetBrains Mono*.
- **Sin Build Step Pesado**: React 19 se ejecuta directamente mediante módulos ESM nativos del navegador, garantizando rendimiento instantáneo y cero complejidad de empaquetado.
- **Auto-Healing & Health Doctor**: Diagnóstico en 7 áreas clave con botón de auto-remediación a 100% de salud.

---

## 📑 Pestañas del Panel

1. **📊 Overview**: Estado global de CPU, RAM, motores de inferencia, score de salud y acciones rápidas de reparación.
2. **🦙 Ollama Hub**: Monitoreo de modelos descargados, descarga de nuevos modelos (`pull`), descarga de VRAM y benchmarks.
3. **🧠 Modelos & Roles**: Asignación de modelos especializados por tarea (Chat general, Coder, Vision, Router) y pruebas de velocidad.
4. **🔌 MCPs & Herramientas**: Explorador interactivo estilo IDE de los servidores MCP registrados, activación/desactivación de tools y ejecutor de prueba con schema JSON.
5. **💬 ADA Chat**: Chat interactivo con streaming Server-Sent Events (SSE) y renderizado de respuestas.
6. **📱 Telegram Bot**: Panel de control del bot de Telegram (iniciar, detener, reiniciar, verificar token con `getMe`).
7. **🗃️ Memoria & Auditoría**: Visor de base de datos SQLite y auditoría de eventos.
8. **⚙️ Configuración**: Ajustes del agente y rutas permitidas.
