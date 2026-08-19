"""Publish through a configured local Puppeteer/Node boundary after confirmation."""

from src.ada.infrastructure.integrations.instagram import publish


def run(args):
    return publish(
        args.get("config", {}), args.get("image", ""), args.get("caption", ""), confirm=bool(args.get("confirm"))
    )
