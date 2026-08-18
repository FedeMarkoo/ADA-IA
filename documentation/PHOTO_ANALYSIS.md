# Photo analysis

## Entrada

Se acepta una imagen individual o una carpeta con imágenes. Para RAW se usa
`rawpy`; para imágenes terminadas se usa Pillow. La capa técnica no necesita
internet ni un modelo visual.

```python
from skills.photos.analyze_photo import run

result = run({
    "path": "/ruta/evento/_DSC0001.ARW",
    "folder": "/ruta/evento",
    "vision": True,
})
```

## Salida

La revisión incluye:

- enfoque y posible trepidación;
- exposición, sombras y altas luces;
- contraste y composición técnica;
- ISO, cámara, lente y otros datos disponibles;
- sujeto, contexto y tipo de evento;
- coincidencia estimada con la carpeta analizada;
- feedback fotográfico;
- puntuación técnica y puntuación de selección de 1 a 5.

La puntuación no es una orden de descarte automática. Un RAW subexpuesto puede
ser recuperable y un ISO alto puede seguir siendo válido si el momento,
expresión o composición lo justifican. El criterio final distingue entre
`Seleccionada`, `Rechazada` y revisión manual.

## RAW frente a JPG

El RAW conserva más información para recuperar sombras y ajustar exposición.
Por eso ADA aplica un criterio más tolerante al RAW que al JPG terminado. El
ruido se interpreta junto con ISO y cámara: los perfiles actuales son priors
moderados, no una afirmación universal sobre todas las cámaras Sony o Nikon.

La comparación RAW/JPG de una misma toma debe considerar que el JPG puede tener
reducción de ruido, enfoque y compresión aplicados.

## Contexto y sesión

El agente visual usa la ruta, nombre de carpeta, fecha disponible y contenido de
la imagen. Puede distinguir, por ejemplo, una banda, un cumpleaños o un evento
social. La coincidencia es probabilística: una foto puede pertenecer al evento
sin que el modelo pueda identificar con certeza el lugar o las personas.

## Lotes

```text
Seleccioná las fotos de "/ruta/evento" y generá XMP por cada archivo.
```

El lote no usa un límite fijo de fotos buenas. Cada archivo pasa por el mismo
workflow individual y su XMP se escribe al completar ese archivo. Si una foto
falla, el resto del lote continúa y el resultado informa los errores.
