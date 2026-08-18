"""Compatibility entrypoint; use src.ada.interfaces.web.server."""
from src.ada.interfaces.web.server import app, main

if __name__ == '__main__':
    main()
