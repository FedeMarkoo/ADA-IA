# XMP and burst detection

## XMP compatible con Lightroom

Para cada imagen se crea un sidecar junto al archivo, por ejemplo:

```text
_DSC0001.ARW
_DSC0001.xmp
```

ADA actualiza o crea estos campos:

- `xmp:Rating`: 0 para rechazada o el rating de selección para aceptada;
- `xmp:Label`: estado ADA o `Amarillo` para una ráfaga;
- `xmpDM:good`: `True` para seleccionada y `False` para rechazada;
- `ada:Status`, `ada:Score` y `ada:Reason`: información propia de ADA.

El sidecar se genera archivo por archivo, no al final del lote. Se preservan
otros campos XMP no administrados por ADA.

## Señales de ráfaga

El detector está en `skills/photos/burst_detection.py`. La numeración `_DSC####`
solo genera candidatos; por sí sola no alcanza para declarar una ráfaga.
Luego se buscan, en orden de evidencia:

1. MakerNotes de cámara: secuencia, número de disparo y modo continuo;
2. fecha y hora de captura, idealmente con subsegundos;
3. similitud visual entre cuadros adyacentes;
4. cercanía de números de secuencia como condición de vecindad.

Los grupos se fusionan cuando comparten cuadros. El resultado también devuelve
`burst_detection`, con cantidad de candidatos, disponibilidad de ExifTool y la
señal que justificó cada grupo.

## ExifTool opcional

Si `exiftool` está instalado, ADA lo invoca en modo JSON para leer MakerNotes de
Sony y otras cámaras. Si no está instalado, usa el tiempo que `rawpy` pueda
leer y la similitud visual. En ese modo conservador puede no marcar una ráfaga
real antes que marcar como ráfaga una secuencia que solo comparte numeración.

## Reparación y regeneración

Reparar XMP conserva el análisis existente y corrige los flags de Lightroom.
Regenerar XMP implica eliminar los sidecars del lote y volver a analizar los
RAW. Los RAW nunca deben borrarse para realizar esta operación.

Ejemplo de validación:

```bash
find /ruta/evento -maxdepth 1 -iname '*.xmp' | wc -l
find /ruta/evento -maxdepth 1 -iname '*.xmp' -print0 \
  | xargs -0 -n1 xmllint --noout
```
