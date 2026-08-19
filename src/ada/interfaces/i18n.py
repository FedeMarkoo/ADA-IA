"""Minimal message catalog shared by interfaces; prompts remain configurable."""

MESSAGES = {
    "es": {
        "greeting": "Hola, ¿en qué puedo ayudarte?",
        "empty_message": "El mensaje no puede estar vacío.",
        "processing": "ADA está procesando el pedido.",
    },
    "en": {
        "greeting": "Hi, how can I help you?",
        "empty_message": "The message cannot be empty.",
        "processing": "ADA is processing your request.",
    },
}


def normalize_language(language):
    value = str(language or "es").lower().split("-", 1)[0]
    return value if value in MESSAGES else "es"


def tr(key, language="es", **values):
    message = MESSAGES[normalize_language(language)].get(key, MESSAGES["es"].get(key, key))
    return message.format(**values) if values else message
