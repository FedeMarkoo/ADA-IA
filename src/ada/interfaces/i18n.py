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
    },
    "en": {
        "greeting": "Hi, how can I help you?",
        "empty_message": "The message cannot be empty.",
        "processing": "ADA is processing your request.",
        "status_received": "I received your request and am identifying the task.",
        "status_progress": "The task is still running. ADA continues working.",
        "path_required": "I need the path or folder to execute that task.",
        "confirmation_required": "The operation is ready. It is sensitive; reply 'confirm' to execute it.",
    },
}


def normalize_language(language):
    value = str(language or "es").lower().split("-", 1)[0]
    return value if value in MESSAGES else "es"


def tr(key, language="es", **values):
    message = MESSAGES[normalize_language(language)].get(key, MESSAGES["es"].get(key, key))
    return message.format(**values) if values else message
