# sqlite

Tool de consulta de bases SQLite en modo exclusivamente lectura.

Acciones disponibles:

- `status`: resumen de la biblioteca y sus formatos.
- `structure`: colecciones, metadata y rutas registradas.
- `report`: reporte completo con conteos reales por formato y carpeta.

La tool abre la base con `mode=ro`. No modifica la base ni ejecuta el script de Lightroom. Las operaciones sobre archivos siguen siendo responsabilidad de `lightroom` y `filesystem`.
