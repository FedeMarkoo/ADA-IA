"""Send Gmail only after an explicit confirmation, returning a preview otherwise."""
from src.ada.infrastructure.integrations.gmail import send


def run(args):
    return send(args.get('config', {}), args.get('to', ''), args.get('subject', ''),
                args.get('body', ''), confirm=bool(args.get('confirm')))
