---
name: organize_photos
description: Organiza fotos por palabras clave en el nombre de archivo (wedding, vacation, birthday, concert, family, etc.)
params:
  - dir: string (requerido) — carpeta con fotos a ordenar
risk: low
permissions: filesystem
examples:
  - run: .venv/bin/python -c "from ada.capabilities.photography.organize_photos import run; print(run({'dir':'/ruta/a/fotos'}))"
---

Esta skill mueve las imágenes a `organized/<category>/` según coincidencias simples en el nombre del archivo.
