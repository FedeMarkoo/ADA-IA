# 🛡️ 01. Seguridad y Privacidad

## Estado de Implementación

| ID | Mejora / Corrección | Estado | Commit |
|---|---|---|---|
| SEC-01 | Purgar `ada/config.json` y datos personales de TODO el historial de Git | ✅ Implementado | `620070c` |
| SEC-02 | Excluir `ada/config.json` y `config.json` en `.gitignore` | ✅ Implementado | `620070c` |
| SEC-03 | Reemplazar rutas de usuario absolutas hardcodeadas por `Path.home()` | ✅ Implementado | `620070c` |
| SEC-04 | Anonimizar datos personales en prompts de `ai_testing/prompts.json` | ✅ Implementado | `620070c` |
| SEC-05 | Rate-limiting y throttling en mutaciones de la Bóveda de Credenciales | ✅ Implementado | `En este branch` |
| SEC-06 | Token de autenticación interno para webhook/REST API de Telegram | ✅ Implementado | `En este branch` |
| SEC-07 | Modo de visualización embebida local de Grafana para Desktop | ℹ️ Documentado | Diseño activo |

---

## Detalle de Implementaciones

### SEC-01 & SEC-02: Purga y Exclusión de `config.json`
- **Problema**: El archivo de configuración de producción con el chat ID de Telegram y rutas personales estaba commiteado en el historial de Git.
- **Solución**: Se ejecutó `git filter-branch` con reescritura de árboles y recolección de basura agresiva. Se añadió regla estricta a `.gitignore` permitiendo únicamente `config.example.json` y `mcps/config.json`.

### SEC-03: Rutas de Usuario Dinámicas
- **Problema**: `mcps/git/manager.py` contenía rutas fijas hacia `/home/fedemarkoo/...`.
- **Solución**: Migración a `Path.home() / ".local/usr/..."` asegurando portabilidad en cualquier máquina o usuario.

### SEC-05 & SEC-06: Hardening de API Interna y Bóveda
- Se implementó validación de origen/host estricta, CSRF token verificado con `secrets.compare_digest()`, y throttling en creación de secretos.
- La comunicación entre el adaptador de Telegram y la API REST utiliza cabeceras y validación de origen local protegidas.

### SEC-07: Grafana Embebido
- **Decisión de Diseño**: Grafana está configurado con `GF_AUTH_ANONYMOUS_ENABLED: "true"` y `GF_SECURITY_ALLOW_EMBEDDING: "true"` para permitir que el visor webview GTK/Desktop de ADA renderice los dashboards de monitoreo de Prometheus sin requerir un login secundario en la interfaz de escritorio.
