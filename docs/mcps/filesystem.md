# MCP Filesystem

El servidor MCP **`mcps/filesystem/`** provee herramientas seguras para interactuar con el sistema de archivos local, con validación de rutas autorizadas (`allowed_roots`) y protección contra colisiones.

---

## 🛠️ Herramientas Expuestas

### 1. `filesystem.list_files`
- **Descripción**: Lista archivos y carpetas dentro de directorios permitidos.
- **Riesgo**: `safe`.

### 2. `filesystem.read_file`
- **Descripción**: Lee el contenido en texto plano de un archivo local.
- **Riesgo**: `safe`.

### 3. `filesystem.write_file`
- **Descripción**: Escribe o actualiza un archivo en el disco.
- **Riesgo**: `confirmation`.

### 4. `filesystem.move_files`
- **Descripción**: Mueve o renombra archivos respetando las carpetas raíz autorizadas.
- **Riesgo**: `confirmation`.

### 5. `filesystem.group_files`
- **Descripción**: Agrupa y consolida los archivos de un directorio en una subcarpeta nombrada, evitando sobreescrituras accidentales con sufijos numéricos automáticos.
- **Riesgo**: `confirmation`.
