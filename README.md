# ADA

ADA es un asistente local y extensible construido con Kotlin y Spring Boot.
El proyecto se reinicia desde cero manteniendo los principios del sistema
anterior: local-first, privacidad, modularidad, trazabilidad, reversibilidad y
uso responsable de recursos.

## Estado actual

Esta primera iteración define la arquitectura, las reglas de desarrollo y los
contratos operativos. La implementación funcional se incorporará por cortes
pequeños y verificables.

## Documentación

- [Arquitectura](docs/architecture.md)
- [Reglas de código](docs/coding-rules.md)
- [Observabilidad y métricas](docs/observability.md)
- [Integraciones y configuración](docs/integrations.md)
- [Decisiones de arquitectura](docs/decisions/README.md)

## Principios no negociables

1. El dominio no conoce Spring, SQLite, LiteLLM ni proveedores externos.
2. Las dependencias apuntan hacia el dominio y los casos de uso.
3. Los componentes extensibles se consumen mediante listas de interfaces,
   nunca mediante `if`/`when` centralizados que conozcan todas las variantes.
4. Toda operación relevante deja métricas, logs estructurados y, cuando
   corresponde, un registro de auditoría.
5. Los datos locales viven fuera del repositorio mediante `ADA_DATA_DIR`.
6. Los secretos llegan por variables de entorno o un gestor externo; nunca por
   archivos versionados.

## Comandos previstos

```bash
mvn test
mvn verify
```

El despliegue local de LiteLLM y el layout de datos están documentados en
[Integraciones y configuración](docs/integrations.md).
