# Mejoras

## MCP

- [x] Compatibilidad con definiciones de servidores estilo VS Code para MCP `stdio`.
- [x] Soporte de `command`, `args`, `env` y `cwd` en servidores locales.
- [x] Resolución de variables `${env:NAME}` completas o incrustadas desde el entorno de ADA.
- [x] Compatibilidad inicial con MCP remoto mediante Streamable HTTP.
- [x] Backend MCP opcional dentro de las capabilities canónicas de Gmail, sin routing duplicado.
- [x] Importar `.vscode/mcp.json` sólo con opt-in explícito del workspace.
- [ ] Resolver de forma segura `${input:NAME}` con un mecanismo de configuración/secretos de ADA.
- [ ] Mantener procesos MCP persistentes para evitar arrancar un proceso nuevo por cada llamada.
- [ ] Exponer las tools MCP descubiertas al planner/router como capabilities dinámicas, con schemas y nivel de riesgo.
- [ ] Agregar gestión de lifecycle, health checks y reconexión para servidores MCP remotos.

## Lightroom → MCP independiente

La capability existente es la implementación canónica y el **Lightroom MCP
Server** es una interfaz externa delgada que reutiliza esa misma validación. ADA
llama directamente a la capability; VS Code y otros hosts usan el MCP, que
aplica allowlist y auditoría dentro de su propio proceso.

### Estado

- [x] Crear un servidor MCP de Lightroom ejecutable por separado mediante `ada-lightroom-mcp`.
- [x] Exponer operaciones de conteo, análisis, planificación, simulación,
  aplicación y recuperación como tools MCP.
- [x] Mantener confirmación explícita para operaciones mutantes.
- [x] Documentar la configuración de Lightroom como servidor MCP de VS Code/ADA.
- [x] Definir la capability existente como adaptador canónico y el MCP como
  interfaz externa del mismo código.
- [ ] Extraer el servicio de fotografía/Lightroom a un paquete independiente,
  sin dependencias del runtime de ADA.
- [ ] Publicar el Lightroom MCP como proyecto/repo independiente cuando el
  contrato de tools esté estabilizado.

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

### Arquitectura elegida

```text
ADA router/planner ──────────────┐
                                ▼
                         Lightroom adapter
                                ▲
VS Code / MCP hosts ─ MCP server┘
```

### Reglas de migración

1. Mantener una sola implementación de reglas y ejecución; las interfaces sólo
   delegan.
2. Mantener `plan` y `simulate` como operaciones sin mutaciones.
3. Toda escritura de archivos, catálogo o XMP debe poder identificarse en un
   manifiesto y ser reversible cuando sea técnicamente posible.
4. El MCP debe poder ejecutarse de manera independiente de ADA para permitir
   pruebas, CLI y otros clientes MCP. El servidor de este PR sigue reutilizando
   temporalmente el adaptador existente; la extracción del servicio es el paso
   siguiente.
5. El MCP publica schemas propios sin crear una segunda capability en el router
   de ADA.
6. La migración debe conservar las validaciones actuales de RAW/JPG/XMP y las
   reglas para evitar asociaciones incorrectas por nombre base.

### Orden recomendado

1. [x] Mantener la capability como adaptador canónico de ejecución.
2. [x] Crear el servidor MCP con `stdio` como transporte inicial.
3. [x] Aplicar allowlist, confirmación, límites y auditoría dentro del servidor.
4. [ ] Extraer la lógica canónica a un paquete independiente si el servidor se
   publica fuera del repositorio.
5. [ ] Hacer que ambos adaptadores dependan de ese paquete sin cambiar sus
   contratos públicos.
