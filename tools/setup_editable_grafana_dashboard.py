#!/usr/bin/env python3
"""Script to import the ADA overview dashboard as a fully editable Grafana dashboard."""
import json
import base64
import urllib.request
import urllib.error
import sys
from pathlib import Path

GRAFANA_URL = "http://127.0.0.1:3000"
AUTH = base64.b64encode(b"admin:admin").decode("ascii")

def main():
    json_path = Path(__file__).resolve().parent.parent / "monitoring" / "grafana" / "dashboards" / "ada-overview.json"
    if not json_path.exists():
        print(f"❌ No se encontró el archivo: {json_path}")
        sys.exit(1)

    with open(json_path, "r", encoding="utf-8") as f:
        dash_content = json.load(f)

    # Ensure clean editable configuration
    dash_content["uid"] = "ada-overview"
    dash_content["title"] = "ADA — Operaciones"
    dash_content["editable"] = True
    dash_content["id"] = None
    dash_content["version"] = 1

    payload = json.dumps({
        "dashboard": dash_content,
        "overwrite": True,
        "message": "Dashboard editable inicializado para ADA"
    }).encode("utf-8")

    req = urllib.request.Request(f"{GRAFANA_URL}/api/dashboards/db", data=payload, method="POST")
    req.add_header("Authorization", f"Basic {AUTH}")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            print(f"✅ Dashboard creado exitosamente!")
            print(f"🔗 URL Interna: {GRAFANA_URL}{data.get('url', '/d/ada-overview')}")
            print(f"✏️  Estado: 100% Editable desde la interfaz web de Grafana.")
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"❌ Error HTTP {e.code}: {err}")
        if "provisioned" in err.lower():
            print("\n⚠️  El archivo de aprovisionamiento aún está bloqueando la modificación.")
            print("Ejecuta en tu terminal:\n  sudo rm -f /etc/grafana/provisioning/dashboards/dashboards.yaml\n  sudo systemctl restart grafana-server")
    except Exception as e:
        print(f"❌ Error al conectar con Grafana: {e}")

    # Ensure public dashboard (Share externally) exists
    pub_req = urllib.request.Request(f"{GRAFANA_URL}/api/dashboards/uid/ada-overview/public-dashboards")
    pub_req.add_header("Authorization", f"Basic {AUTH}")
    token = None
    try:
        with urllib.request.urlopen(pub_req) as resp:
            data = json.loads(resp.read().decode())
            if isinstance(data, list) and data:
                token = data[0].get("accessToken")
            elif isinstance(data, dict) and data.get("accessToken"):
                token = data.get("accessToken")
    except urllib.error.HTTPError:
        pass

    if not token:
        pub_payload = json.dumps({
            "isEnabled": True,
            "timeSelectionEnabled": True,
            "annotationsEnabled": False,
            "share": "public"
        }).encode("utf-8")
        create_pub_req = urllib.request.Request(f"{GRAFANA_URL}/api/dashboards/uid/ada-overview/public-dashboards", data=pub_payload, method="POST")
        create_pub_req.add_header("Authorization", f"Basic {AUTH}")
        create_pub_req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(create_pub_req) as resp:
                data = json.loads(resp.read().decode())
                token = data.get("accessToken")
        except Exception as e:
            print(f"⚠️ No se pudo crear el public dashboard: {e}")

    if token:
        print(f"🌐 Public Dashboard URL (Sin Login): {GRAFANA_URL}/public-dashboards/{token}")

if __name__ == "__main__":
    main()
