"""Send Gmail only after an explicit confirmation, returning a preview otherwise."""

from ada.infrastructure.integrations.gmail import send


CAPABILITY_SPEC = {
    "name": "gmail_send",
    "description": "Enviar un correo de Gmail después de confirmación explícita",
    "risk_level": "high",
    "requires_confirmation": True,
    "permissions": ["gmail.send"],
}


def run(args):
    return send(
        args.get("config", {}),
        args.get("to", ""),
        args.get("subject", ""),
        args.get("body", ""),
        confirm=bool(args.get("confirm")),
    )
