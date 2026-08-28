# ADR-002: SQLite fuera del repositorio

- Estado: aceptada
- Fecha: 2026-08-28

## Contexto

La base contiene memoria, auditoría y datos operativos que no deben mezclarse
con el código ni perderse al recrear el checkout.

## Decisión

El layout persistente vive bajo `ADA_DATA_DIR`, con subcarpetas segregadas para
DB, logs, backups, exports, models y runtime. La aplicación crea el layout y
valida permisos al iniciar.

## Consecuencias

El repositorio queda reproducible y los datos sobreviven a un reinicio del
código. Backup, permisos y limpieza pasan a ser responsabilidades operativas
explícitas.
