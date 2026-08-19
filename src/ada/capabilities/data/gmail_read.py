"""Read Gmail metadata with the least-privilege read scope."""

from src.ada.infrastructure.integrations.gmail import read


def run(args):
    return read(args.get("config", {}), query=args.get("query", "is:unread"), limit=args.get("limit", 10))
