"""Read Gmail metadata with the least-privilege read scope."""

from ada.infrastructure.integrations.gmail import read


CAPABILITY_SPEC = {
    "name": "gmail_read",
    "description": "Leer Gmail mediante el backend canónico configurado",
    "risk_level": "low",
    "requires_confirmation": False,
    "permissions": ["gmail.read"],
}


def run(args):
    return read(args.get("config", {}), query=args.get("query", "is:unread"), limit=args.get("limit", 10))
