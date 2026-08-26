"""Modular Photography & Lightroom MCP Stdio JSON-RPC Server."""

import sys
from pathlib import Path

# Ensure project root is in sys.path when executed directly
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcps.protocol import StdioMCPServer
from mcps.photography.analyzer import PhotoAnalyzer
from mcps.photography.batch import BatchProcessor
from mcps.photography.burst import BurstDetector
from mcps.photography.xmp import XmpManager
from mcps.photography.organizer import PhotoOrganizer
from mcps.photography.lightroom import LightroomManager


def create_photography_server() -> StdioMCPServer:
    server = StdioMCPServer("photography", "2.0.0")

    # 1. Single photo analysis
    server.register_tool(
        name="photography.analyze_photo",
        description="Analiza metadata, calidad técnica (enfoque, exposición, ruido) y contenido de una fotografía o archivo RAW.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Ruta de la imagen o archivo RAW (JPG, CR2, NEF, ARW, DNG, etc.)",
                },
                "vision": {
                    "type": "boolean",
                    "description": "Habilitar análisis semántico con VLM local",
                    "default": False,
                },
            },
            "required": ["path"],
        },
        handler=PhotoAnalyzer.analyze,
        risk_level="safe",
    )

    # 2. Batch processing
    server.register_tool(
        name="photography.analyze_batch",
        description="Evalúa y clasifica un lote completo de fotografías en paralelo, puntuando y seleccionando las mejores tomas.",
        parameters={
            "type": "object",
            "properties": {
                "dir": {"type": "string", "description": "Directorio con las fotos a procesar"},
                "limit": {"type": "integer", "description": "Límite máximo de fotos a procesar"},
                "vision": {"type": "boolean", "description": "Habilitar análisis visual VLM", "default": False},
                "write_xmp": {"type": "boolean", "description": "Generar sidecars XMP de Lightroom", "default": True},
            },
            "required": ["dir"],
        },
        handler=BatchProcessor.process_batch,
        risk_level="safe",
    )

    # 3. Burst detection
    server.register_tool(
        name="photography.detect_bursts",
        description="Detecta secuencias de disparos en ráfaga a partir de tiempos de captura, metadata y similitud visual.",
        parameters={
            "type": "object",
            "properties": {
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista de rutas de fotos a analizar para ráfagas",
                },
                "time_threshold": {
                    "type": "number",
                    "description": "Ventana máxima en segundos entre disparos de ráfaga",
                    "default": 2.0,
                },
            },
            "required": ["files"],
        },
        handler=lambda args: {
            "groups": [
                [str(p) for p in grp]
                for grp in BurstDetector.detect_burst_groups(
                    args.get("files", []), float(args.get("time_threshold", 2.0))
                )[0]
            ],
            "ok": True,
        },
        risk_level="safe",
    )

    # 4. Write Lightroom XMP
    server.register_tool(
        name="photography.write_xmp",
        description="Escribe o actualiza un archivo sidecar .xmp compatible con Adobe Lightroom (rating, status, labels).",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Ruta de la foto"},
                "status": {
                    "type": "string",
                    "enum": ["Seleccionada", "Rechazada"],
                    "description": "Estado de selección",
                },
                "rating": {"type": "integer", "description": "Estrellas (0 a 5)"},
                "score": {"type": "number", "description": "Puntaje numérico (0.0 a 10.0)"},
                "reason": {"type": "string", "description": "Motivo de la calificación"},
                "label": {"type": "string", "description": "Etiqueta de color opcional (amarillo, rojo, etc.)"},
            },
            "required": ["path", "status", "rating", "score", "reason"],
        },
        handler=lambda args: {
            "xmp_path": XmpManager.write_photo_xmp(
                args["path"],
                args["status"],
                int(args["rating"]),
                float(args["score"]),
                args["reason"],
                args.get("label"),
            ),
            "ok": True,
        },
        risk_level="safe",
    )

    # 5. Repair Lightroom XMP Flags
    server.register_tool(
        name="photography.repair_xmp",
        description="Repara los flags de Pick/Reject de Lightroom en los sidecars XMP existentes.",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Ruta del archivo a reparar"}},
            "required": ["path"],
        },
        handler=lambda args: {"xmp_path": XmpManager.repair_photo_xmp(args["path"]), "ok": True},
        risk_level="safe",
    )

    # 6. Organize photos
    server.register_tool(
        name="photography.organize_photos",
        description="Organiza fotos en subdirectorios categorizados según palabras clave y eventos.",
        parameters={
            "type": "object",
            "properties": {
                "dir": {"type": "string", "description": "Directorio de fotos a organizar"},
                "dry_run": {"type": "boolean", "description": "Simular sin mover archivos reales", "default": True},
                "confirm": {"type": "boolean", "description": "Confirmación explícita para mover archivos"},
            },
            "required": ["dir"],
        },
        handler=PhotoOrganizer.organize,
        risk_level="confirmation",
        requires_confirmation=True,
    )

    # 7. Lightroom Catalog Management
    server.register_tool(
        name="photography.lightroom_manage",
        description="Audita y planifica la limpieza y sincronización de sidecars en el catálogo de fotos de Lightroom.",
        parameters={
            "type": "object",
            "properties": {
                "root": {"type": "string", "description": "Ruta raíz de las fotos de Lightroom"},
                "action": {"type": "string", "enum": ["plan", "simulate", "clean"], "default": "plan"},
                "confirm": {"type": "boolean", "description": "Confirmación para acciones reales"},
            },
            "required": ["root"],
        },
        handler=LightroomManager.run,
        risk_level="confirmation",
        requires_confirmation=True,
    )

    return server


if __name__ == "__main__":
    srv = create_photography_server()
    srv.run()
