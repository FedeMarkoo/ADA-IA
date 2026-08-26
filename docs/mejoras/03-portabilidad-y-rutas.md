# 🌐 03. Portabilidad y Rutas

## Estado de Implementación

| ID | Mejora / Corrección | Estado | Commit |
|---|---|---|---|
| PORT-01 | Soporte de rutas multiplataforma con `pathlib.Path` | ✅ Implementado | `620070c` |
| PORT-02 | Detección de CPU multiplataforma mediante `psutil` (eliminando `os.getloadavg()`) | ✅ Implementado | `5e34825` |
| PORT-03 | Resolución de ejecutables locales (`ollama`, `git`) con `shutil.which` y búsqueda dinámica | ✅ Implementado | `620070c` |

---

## Detalle de Implementaciones

### PORT-01 & PORT-03: Paths Dinámicos
- Eliminación de presunciones basadas exclusivamente en rutas tipo macOS (`/Volumes/ADA`, `/Users/...`) o Linux (`/home/...`).
- Todo el manejo de archivos utiliza `Path.home()` y `os.path.expanduser()`.
- La configuración permite el uso de `~` tanto en entornos POSIX como Windows.
