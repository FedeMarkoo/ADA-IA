"""Minimal message catalog shared by interfaces; prompts remain configurable."""

MESSAGES = {
    "es": {
        "greeting": "Hola, ¿en qué puedo ayudarte?",
        "empty_message": "El mensaje no puede estar vacío.",
        "processing": "ADA está procesando el pedido.",
        "status_received": "Recibí tu pedido. Estoy entendiendo qué tarea corresponde.",
        "status_progress": "La tarea sigue en ejecución. ADA continúa trabajando.",
        "path_required": "Necesito la ruta o carpeta para ejecutar esa tarea.",
        "confirmation_required": "Preparé la operación. Es una acción sensible; respondé 'confirmo' para ejecutarla.",
        "cancelled": "Operación cancelada.",
    },
    "en": {
        "greeting": "Hi, how can I help you?",
        "empty_message": "The message cannot be empty.",
        "processing": "ADA is processing your request.",
        "status_received": "I received your request and am identifying the task.",
        "status_progress": "The task is still running. ADA continues working.",
        "path_required": "I need the path or folder to execute that task.",
        "confirmation_required": "The operation is ready. It is sensitive; reply 'confirm' to execute it.",
        "cancelled": "Operation cancelled.",
    },
}


import logging

logger = logging.getLogger("ada.i18n")


def normalize_language(language):
    value = str(language or "es").lower().split("-", 1)[0]
    return value if value in MESSAGES else "es"


def tr(key, language="es", **values):
    lang_code = normalize_language(language)
    message = MESSAGES.get(lang_code, {}).get(key) or MESSAGES.get("es", {}).get(key)
    if message is None:
        logger.debug("missing_translation_key key=%s lang=%s", key, language)
        message = str(key)
    return message.format(**values) if values else message
