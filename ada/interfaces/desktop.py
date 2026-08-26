"""Desktop shell for ADA.

The dashboard remains a normal local web application, but this module hosts it
inside the operating system WebKitGTK webview. This avoids starting Chrome just
to use ADA while keeping the web URL available for remote/browser access.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any

from werkzeug.serving import make_server

LOGGER = logging.getLogger("ada.desktop")


def _load_gtk():
    """Load GTK 3 and WebKit2 lazily so the normal CLI stays dependency-free."""

    try:
        import gi

        gi.require_version("Gtk", "3.0")
        gi.require_version("WebKit2", "4.1")
        from gi.repository import Gio, Gtk, WebKit2
    except Exception as exc:  # pragma: no cover - depends on host packages
        raise SystemExit(
            "La app de escritorio necesita GTK 3 + WebKitGTK 4.1. "
            "En Debian/Ubuntu instalá: sudo apt install python3-gi gir1.2-gtk-3.0 "
            "gir1.2-webkit2-4.1"
        ) from exc
    return Gio, Gtk, WebKit2


def _start_server(app: Any, host: str, requested_port: int):
    server = make_server(host, requested_port, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, name="ada-web", daemon=True)
    thread.start()
    return server, thread


def run() -> None:
    """Start ADA's local API and show its dashboard in a native window."""

    Gio, Gtk, WebKit2 = _load_gtk()

    # Importing the Flask module initializes the same ADA runtime used by
    # ``ada serve``. It is intentionally delayed until the desktop command is
    # selected, so ordinary CLI commands do not pay that startup cost.
    from ada.interfaces.web.server import app

    host = os.environ.get("ADA_UI_HOST", "127.0.0.1")
    requested_port = int(os.environ.get("ADA_UI_PORT", "5005"))
    try:
        server, server_thread = _start_server(app, host, requested_port)
    except (OSError, SystemExit):
        if requested_port != 0:
            LOGGER.warning("El puerto %s está ocupado; buscando uno libre", requested_port)
            server, server_thread = _start_server(app, host, 0)
        else:
            raise

    url = f"http://{host}:{server.server_port}/"
    application = Gtk.Application(
        application_id="com.ada.gestor",
        flags=Gio.ApplicationFlags.FLAGS_NONE,
    )
    window_holder = {}

    def close(*_args):
        server.shutdown()
        if server_thread.is_alive():
            server_thread.join(timeout=2)
        application.quit()
        return False

    def activate(app_instance):
        window = window_holder.get("window")
        if window is None:
            window = Gtk.ApplicationWindow(application=app_instance, title="ADA")
            window.set_default_size(1440, 920)
            window.set_position(Gtk.WindowPosition.CENTER)
            window.connect("delete-event", close)

            webview = WebKit2.WebView()
            webview.set_hexpand(True)
            webview.set_vexpand(True)
            window.add(webview)
            window_holder["window"] = window
            window.show_all()
            webview.load_uri(url)
        else:
            window.present()

    application.connect("activate", activate)
    LOGGER.info("ADA Desktop disponible en %s", url)
    print(f"ADA Desktop: {url}")
    application.run([])
