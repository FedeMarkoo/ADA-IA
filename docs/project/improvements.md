# Mejoras

## MCP

- [x] Compatibilidad con definiciones de servidores estilo VS Code para MCP `stdio`.
- [x] Soporte de `command`, `args`, `env` y `cwd` en servidores locales.
- [x] Resolución de variables `${env:NAME}` desde el entorno de ADA.
- [x] Compatibilidad inicial con MCP remoto mediante Streamable HTTP.
- [ ] Importar automáticamente `.vscode/mcp.json` sin copiar la configuración a `config.json`.
- [ ] Resolver de forma segura `${input:NAME}` con un mecanismo de configuración/secretos de ADA.
- [ ] Mantener procesos MCP persistentes para evitar arrancar un proceso nuevo por cada llamada.
- [ ] Exponer las tools MCP descubiertas al planner/router como capabilities dinámicas, con schemas y nivel de riesgo.
- [ ] Agregar gestión de lifecycle, health checks y reconexión para servidores MCP remotos.

## Lightroom → MCP independiente

La integración actual de Lightroom está demasiado cerca del núcleo de ADA: la
capability conoce reglas de organización, SQLite, XMP, RAW/JPG, verificación y
el ejecutor `gestor_fotos_lightroom.py`. La dirección recomendada es separar esa
responsabilidad en un **Lightroom MCP Server** independiente.

### Objetivo

Convertir las operaciones específicas de Lightroom/fotografía en tools MCP y
hacer que ADA actúe como cliente/orquestador. ADA debería decidir *qué* quiere
hacer y el MCP de Lightroom debería encargarse de *cómo* interactuar con el
catálogo, XMP y archivos.

### Tools propuestas

- `lightroom.inspect_session` — inspeccionar RAW/JPG/XMP/videos/editables y contexto.
- `lightroom.analyze_catalog` — consultar el estado del catálogo y SQLite.
- `lightroom.plan_organization` — generar un plan sin modificar archivos.
- `lightroom.simulate_organization` — validar el plan en dry-run.
- `lightroom.apply_organization` — ejecutar una organización confirmada.
- `lightroom.validate_organization` — verificar origen, destino, cantidades y duplicados.
- `lightroom.generate_xmp` — crear/actualizar sidecars XMP.
- `lightroom.recover` — recuperar una operación usando su manifiesto/undo.
- `lightroom.list_photos` — consultar fotografías y metadatos relevantes.

### Arquitectura objetivo

```text
ADA
 ├─ router / planner
 ├─ memoria / auditoría / confirmación
 └─ MCP client
       │
       ▼
Lightroom MCP Server
 ├─ photo/session analysis
 ├─ Lightroom catalog + SQLite
 ├─ RAW/JPG/XMP operations
 ├─ organization + validation
 └─ manifests / recovery
```

### Reglas de migración

1. No mover la lógica de negocio a ADA nuevamente después de extraerla.
2. Mantener `plan` y `simulate` como operaciones sin mutaciones.
3. Toda escritura de archivos, catálogo o XMP debe poder identificarse en un
   manifiesto y ser reversible cuando sea técnicamente posible.
4. El MCP debe poder ejecutarse de manera independiente de ADA para permitir
   pruebas, CLI y otros clientes MCP.
5. ADA debe consumir schemas de las tools y no duplicar manualmente sus
   argumentos.
6. La migración debe conservar las validaciones actuales de RAW/JPG/XMP y las
   reglas para evitar asociaciones incorrectas por nombre base.

### Orden recomendado

1. Extraer primero las funciones puras de análisis/validación.
2. Crear el servidor MCP de Lightroom con `stdio` como transporte inicial.
3. Migrar `plan`, `simulate` y `validate`.
4. Migrar las operaciones de escritura y recuperación.
5. Hacer que ADA consuma exclusivamente el MCP para Lightroom.
6. Eliminar progresivamente la capability Lightroom interna y actualizar la
   documentación.
