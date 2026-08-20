"""Boundary adapter for the user's existing Node/Puppeteer publisher."""

import os
import subprocess
from pathlib import Path


def publish(config, image, caption, confirm=False):
    if config.get("instagram_provider") == "graph":
        from ada.infrastructure.integrations.instagram_graph import publish as graph_publish

        return graph_publish(config, image, caption, confirm=confirm)
    preview = {"image": str(image), "caption": str(caption)}
    if not confirm:
        return {"error": "confirmation_required", "preview": preview}
    script = config.get("instagram_publish_script")
    if not script:
        return {"error": "instagram_script_not_configured", "preview": preview}
    image_path = Path(os.path.expanduser(str(image))).resolve()
    script_path = Path(os.path.expanduser(str(script))).resolve()
    roots = [Path(os.path.expanduser(str(item))).resolve() for item in config.get("allowed_roots", []) if item]
    if not image_path.is_file() or not script_path.is_file():
        return {"error": "image_or_script_not_found", "image": str(image_path), "script": str(script_path)}
    if roots and not any(image_path == root or root in image_path.parents for root in roots):
        return {"error": "path_outside_allowed_roots", "image": str(image_path)}
    profile_dir = Path(
        os.path.expanduser(str(config.get("instagram_profile_dir", "~/.config/ada/instagram-profile")))
    ).resolve()
    profile_dir.mkdir(parents=True, exist_ok=True)
    try:
        profile_dir.chmod(0o700)
    except OSError:
        pass
    result = subprocess.run(
        [
            "node",
            str(script_path),
            "--image",
            str(image_path),
            "--caption",
            str(caption),
            "--user-data-dir",
            str(profile_dir),
        ],
        capture_output=True,
        text=True,
        timeout=int(config.get("instagram_timeout", 180)),
    )
    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "preview": preview,
        "profile_dir": str(profile_dir),
    }
