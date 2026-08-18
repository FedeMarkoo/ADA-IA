# Operations and tests

## Arrancar ADA

```bash
cd /Users/home/Desktop/ADA
.venv/bin/python ui_server.py
```

La interfaz queda disponible en `http://127.0.0.1:5005/`.

El estado del runtime se consulta en `GET /api/status`. El análisis local puede
funcionar sin Ollama; las respuestas visuales necesitan que el modelo de visión
esté instalado y que el runtime esté disponible.

## Pruebas

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Las pruebas cubren análisis técnico, RAW/JPG, tolerancia de ISO, selección,
generación de XMP, flags Lightroom, carga recursiva de skills y etiquetas de
ráfaga.

## Procesamiento seguro de un lote

Antes de procesar un lote grande:

1. confirmar la ruta exacta;
2. comprobar cuántos RAW contiene;
3. decidir si se quiere análisis visual (`vision=True`) o solo técnico;
4. generar XMP en una carpeta de prueba;
5. validar sidecars antes de abrir Lightroom.

ADA no mueve ni elimina RAW durante la selección. La eliminación de XMP debe
limitarse a la carpeta confirmada por el usuario.
