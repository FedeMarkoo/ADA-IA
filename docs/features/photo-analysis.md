# Análisis de fotos

ADA analiza JPG y RAW con `Pillow` y `rawpy`. La capa local calcula enfoque,
exposición, sombras, altas luces, contraste, orientación, ISO, ruido y una
puntuación técnica. El modelo visual agrega sujeto, contexto, estilo, feedback
como fotógrafo y coincidencia con la carpeta de sesión.

Los RAW reciben un criterio más tolerante porque conservan información de
revelado. ISO, cámara y ruido se consideran junto con el momento y la calidad
artística. Una puntuación no es una orden definitiva de descarte.

## Uso

```text
Analizá la foto "/ruta/evento/_DSC0001.ARW"
Seleccioná las fotos de "/ruta/evento" y generá XMP por cada archivo.
```

Cada foto del lote se analiza individualmente y puede generar su XMP apenas
termina. No existe un cupo fijo de fotos seleccionadas y el lote no mueve ni
elimina RAW.

## Contexto

El agente usa la ruta, carpeta, archivos vecinos y contenido visual para
estimar si la imagen pertenece a la sesión. Puede identificar contextos como
eventos sociales, bandas o coberturas, pero la coincidencia es probabilística y
debe expresarse con confianza, no como certeza inventada.
