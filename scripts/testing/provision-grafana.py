#!/usr/bin/env python3
"""Provision the local ADA dashboard in Grafana."""

import json
import base64
import os
import urllib.request
from pathlib import Path


root = Path(__file__).parents[2]
dashboard = json.loads((root / "monitoring/grafana/dashboards/ada-smoke.json").read_text())
payload = json.dumps({"dashboard": dashboard, "overwrite": True, "folderId": 0}).encode()
request = urllib.request.Request(
    "http://127.0.0.1:3000/api/dashboards/db", data=payload, method="POST"
)
request.add_header("Content-Type", "application/json")
user = os.environ.get("GRAFANA_USER", "admin")
password = os.environ.get("GRAFANA_PASSWORD", "admin")
credentials = base64.b64encode(f"{user}:{password}".encode()).decode()
request.add_header("Authorization", f"Basic {credentials}")
with urllib.request.urlopen(request, timeout=10) as response:
    print(response.read().decode())
