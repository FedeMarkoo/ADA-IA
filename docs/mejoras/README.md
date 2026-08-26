# Índice de mejoras, bugs y roadmap — ADA-IA

Este directorio contiene el registro modular de mejoras, correcciones de seguridad, optimizaciones de arquitectura y roadmap del proyecto.

## Matriz de estado y trazabilidad

| ID | Área / Módulo | Descripción | Estado | Commit / Referencia | Archivo de Detalle |
|---|---|---|---|---|---|
| **SEC-01** | Seguridad | Purgar `config.json` y datos personales de Git | ✅ Implementado | `620070c` | [01-seguridad-y-privacidad.md](01-seguridad-y-privacidad.md) |
| **SEC-02** | Seguridad | Ignorar `ada/config.json` en `.gitignore` | ✅ Implementado | `620070c` | [01-seguridad-y-privacidad.md](01-seguridad-y-privacidad.md) |
| **SEC-03** | Seguridad | Reemplazar rutas de usuario hardcodeadas | ✅ Implementado | `620070c` | [01-seguridad-y-privacidad.md](01-seguridad-y-privacidad.md) |
| **SEC-04** | Seguridad | Anonimizar datos personales en prompts de testing | ✅ Implementado | `620070c` | [01-seguridad-y-privacidad.md](01-seguridad-y-privacidad.md) |
| **SEC-05** | Seguridad | Rate-limiting y protección en Vault API | ✅ Implementado | `En este branch` | [01-seguridad-y-privacidad.md](01-seguridad-y-privacidad.md) |
| **SEC-06** | Seguridad | Autenticación interna Telegram ↔ REST API | ✅ Implementado | `En este branch` | [01-seguridad-y-privacidad.md](01-seguridad-y-privacidad.md) |
| **SEC-07** | Seguridad | Modo visualización embebida Grafana Desktop | ℹ️ Documentado | Diseño activo | [01-seguridad-y-privacidad.md](01-seguridad-y-privacidad.md) |
| **CON-01** | Concurrencia | Sesiones persistentes aisladas por cookie | ✅ Implementado | `4db33d3` | [02-concurrencia-y-persistencia.md](02-concurrencia-y-persistencia.md) |
| **CON-02** | Concurrencia | SQLite WAL mode y locking con RLock | ✅ Implementado | `4db33d3` | [02-concurrencia-y-persistencia.md](02-concurrencia-y-persistencia.md) |
| **PORT-01** | Portabilidad | Rutas dinámicas multiplataforma con `pathlib` | ✅ Implementado | `620070c` | [03-portabilidad-y-rutas.md](03-portabilidad-y-rutas.md) |
| **ARQ-01** | Arquitectura | Modularización de `server.py` en Blueprints | ✅ Implementado | `En este branch` | [04-arquitectura-web-y-blueprints.md](04-arquitectura-web-y-blueprints.md) |
| **MCP-01** | Multiagente | Servidores MCP modulares (Archivos, Fotos, Git, etc.) | ✅ Implementado | `05fa633` | [05-multiagente-y-mcps.md](05-multiagente-y-mcps.md) |
| **OBS-01** | Observabilidad | Telemetría Prometheus + Métricas Grafana | ✅ Implementado | `5e34825` | [06-observabilidad-y-monitoreo.md](06-observabilidad-y-monitoreo.md) |
| **CI-01** | DevOps | Corrección de rutas en pipeline GitHub Actions | ✅ Implementado | `620070c` | [06-observabilidad-y-monitoreo.md](06-observabilidad-y-monitoreo.md) |
| **JARV-01**| Visión Futura | Hoja de ruta de autonomía asistida (JARVIS) | 🚀 En Roadmap | Fase 1-4 | [07-roadmap-jarvis.md](07-roadmap-jarvis.md) |
| **UPD-01** | Infraestructura | Actualización automática y reinicio coordinado | ✅ Implementado | `ada/infrastructure/update` | [08-auto-update.md](08-auto-update.md) |
| **CTX-01** | Memoria | Shared Context y Dynamic Memory para multi-modelo | ✅ Implementado | `ada/application/context_manager` | [09-shared-context-memory.md](09-shared-context-memory.md) |
| **SEC-08** | Seguridad | Defaults fail-closed y defensa en profundidad para tools/API | 🔴 Prioritario | Auditoría 2026-08 | [10-seguridad-fail-closed.md](10-seguridad-fail-closed.md) |
| **PERF-01** | Performance | Concurrencia, cachés, streaming y resiliencia del runtime | 🟠 Priorizado | Auditoría 2026-08 | [11-performance-y-resiliencia.md](11-performance-y-resiliencia.md) |
| **ARQ-04** | Arquitectura | Registro único de tools y routing estructurado sin regex | 🟡 Propuesto | Diseño 2026-08 | [12-registro-de-tools-y-routing.md](12-registro-de-tools-y-routing.md) |

---

## Archivos de detalle

1. [01. Seguridad y privacidad](01-seguridad-y-privacidad.md)
2. [02. Concurrencia y persistencia](02-concurrencia-y-persistencia.md)
3. [03. Portabilidad y rutas](03-portabilidad-y-rutas.md)
4. [04. Arquitectura web y Blueprints](04-arquitectura-web-y-blueprints.md)
5. [05. Multiagente y MCPs](05-multiagente-y-mcps.md)
6. [06. Observabilidad y monitoreo](06-observabilidad-y-monitoreo.md)
7. [07. Roadmap de autonomía (JARVIS)](07-roadmap-jarvis.md)
8. [08. Actualización automática y reinicio](08-auto-update.md)
9. [09. Shared Context y Dynamic Memory](09-shared-context-memory.md)
10. [10. Seguridad fail-closed](10-seguridad-fail-closed.md)
11. [11. Performance y resiliencia](11-performance-y-resiliencia.md)
12. [12. Registro de tools y routing](12-registro-de-tools-y-routing.md)
