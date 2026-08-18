# XMP y ráfagas

Para cada imagen se crea un sidecar junto al RAW:

```text
_DSC0001.ARW
_DSC0001.xmp
```

ADA escribe `xmp:Rating`, `xmp:Label`, `xmpDM:good`, `ada:Status`, `ada:Score`
y `ada:Reason`. Los XMP se generan archivo por archivo y deben ser XML válido
para que Lightroom los detecte.

## Detección de ráfagas

`src/ada/capabilities/photography/burst_detection.py` no considera suficiente la numeración
`_DSC####`. Busca evidencia combinando:

1. MakerNotes y modo continuo de la cámara, si ExifTool está instalado;
2. fecha y hora de captura, idealmente con subsegundos;
3. similitud visual entre cuadros adyacentes;
4. cercanía de números como condición de vecindad.

Los grupos confirmados reciben etiqueta `Amarillo` en Lightroom. Si no hay
evidencia suficiente, ADA debe preferir no marcar antes que pintar cientos de
fotos por una falsa ráfaga.

## Validación

```bash
find /ruta/evento -maxdepth 1 -iname '*.xmp' | wc -l
find /ruta/evento -maxdepth 1 -iname '*.xmp' -print0 | xargs -0 -n1 xmllint --noout
```
