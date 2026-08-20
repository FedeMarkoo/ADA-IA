"""Create a Gmail draft after confirmation."""

from ada.infrastructure.integrations.gmail import draft


CAPABILITY_SPEC = {
    "name": "gmail_draft",
    "description": "Crear un borrador real en Gmail",
    "risk_level": "medium",
    "requires_confirmation": True,
    "permissions": ["gmail.compose"],
}


def run(args):
    return draft(
        args.get("config", {}),
        args.get("to", ""),
        args.get("subject", ""),
        args.get("body", ""),
        confirm=bool(args.get("confirm")),
    )
