---
name: lightroom
description: Planifica y ejecuta el gestor de fotos Lightroom respetando RAW, XMP, SQLite y las reglas del proyecto.
params:
  - action: plan | simulate | count | analyze | organize | mover | limpiar | validar | recuperar
  - root: raíz de Fotos
  - confirm: obligatorio para acciones que modifican archivos o estado
risk: high
permissions: filesystem, subprocess, sqlite
---

Usa `REGLAS_GESTOR_FOTOS.md` y delega en `gestor_fotos_lightroom.py`. Por defecto
planifica con `organizar --simular`; nunca ejecuta una modificación sin confirmación.

El análisis cuenta también JPG/JPEG asociados por nombre base exacto dentro del
mismo registro y registra videos, editables y otros archivos. No se debe usar el
nombre base como asociación global entre sesiones: ante colisiones se agrupan los
JPG por fecha de modificación y se valida el grupo con fecha/contexto y RAW/XMP
de la sesión candidata. La organización completa distribuye esos archivos en
`Fotos`, `Originales`, `Videos` y `Editables`, sin sobrescribir destinos existentes.

## Protocolo de verificación

Antes de informar que una organización terminó correctamente, ADA debe ejecutar
una revisión de solo lectura:

- comparar los RAW físicos de `Originales` con `carpetas.total` de SQLite;
- comprobar la estructura por extensión;
- listar los archivos agrupados por día de modificación y extensión;
- marcar fechas posteriores al evento como advertencias, no como errores automáticos;
- detectar nombres base repetidos entre registros y resolverlos usando fecha,
  contexto, sesión y evidencia RAW/XMP;
- reportar JPG sin RAW, XMP sin RAW y RAW sin JPG;
- después de una corrección, verificar que origen y destino tengan exactamente
  las cantidades esperadas y que no haya duplicados.

Nunca se debe concluir que un movimiento es correcto solamente porque coincide
el nombre del archivo. La revisión debe producir advertencias y errores antes
de permitir otra operación de escritura.
