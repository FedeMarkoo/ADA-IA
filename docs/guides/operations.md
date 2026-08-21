# Operaciones, Diagnóstico y Mantenimiento

ADA-IA incluye herramientas integradas para diagnóstico continuo y auto-remediación automática.

---

## 🩺 Health Doctor y Diagnóstico

El servicio `HealthDoctor` (`ada/interfaces/web/doctor.py`) audita 7 áreas críticas del sistema:

1. **Motor Ollama LLM**: Disponibilidad del socket y latencia HTTP.
2. **Modelos Instalados**: Existencia de al menos un modelo descargado.
3. **Núcleo ADA**: Estado del orquestador y router.
4. **Subconjunto MCP**: Salud y disponibilidad de los servidores de herramientas.
5. **Memoria SQLite**: Integridad de tablas e índices en `ada/memory.db`.
6. **Recursos de Hardware**: Uso de RAM, throttling de CPU y VRAM.
7. **Servicio Telegram Bot**: Conexión del bot y estado de long-polling.

---

## 🛠️ Auto-Remediación

Si algún subsistema se encuentra degradado o detenido, el botón **"Auto-reparar Todo"** del Dashboard ejecuta secuencialmente las acciones de recuperación:
- Iniciar el servicio local de Ollama.
- Levantar los servidores MCP caídos.
- Re-inicializar tablas de memoria.
- Descargar modelos de VRAM si la memoria está saturada.

---

## 💾 Respaldos de la Base de Datos

Para respaldar tu historial de conversaciones, recetas y datos personales:

```bash
# Copia directa segura de SQLite
cp ada/memory.db ~/Desktop/ada_backup_$(date +%Y%m%d).db
```
