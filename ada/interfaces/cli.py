#!/usr/bin/env python3
import argparse
import logging
from datetime import datetime
from pathlib import Path
import os
import json

from ada.infrastructure.persistence.sqlite import Memory
from ada.application.indexer import index_folder, suggest_organization
from ada.application.agent import Agent
from ada.config import load_config as load_validated_config
from ada.application.services.doctor import diagnose, pull_models, prepare_instagram_profile
from ada.infrastructure.integrations.gmail import authenticate
from ada.application.fine_tuning import prepare_dataset, train_lora, validate_dataset

def _find_project_root() -> Path:
    p = Path(__file__).resolve().parent
    for parent in [p, *p.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    return Path(__file__).resolve().parents[3]

PROJECT_ROOT = _find_project_root()


def load_config():
    cfg_path = PROJECT_ROOT / "ada" / "config.json" if (PROJECT_ROOT / "ada" / "config.json").exists() else PROJECT_ROOT / "config.json"
    default_db = str(Path.home() / "Desktop" / "ADA_Data" / "memory.db")
    try:
        return load_validated_config(cfg_path, PROJECT_ROOT)
    except (OSError, ValueError) as exc:
        logging.getLogger("ada.cli").warning("config_load_failed path=%s error=%s", cfg_path, exc)
        return {"name": "ADA", "max_threads": 4, "use_mps": False, "db_path": default_db}


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd")
    p_index = sub.add_parser("index")
    p_index.add_argument("--dir", required=True)
    p_suggest = sub.add_parser("suggest")
    p_suggest.add_argument("--dir", required=True)
    sub.add_parser("run")
    p_serve = sub.add_parser("serve", help="Start the web UI and ADA agent in one process")
    p_serve.add_argument("-debug", "--debug", action="store_true", help="Enable detailed router and model logs")
    p_serve.add_argument("--asgi", action="store_true", help="Use the FastAPI/ASGI interface")
    p_prompt = sub.add_parser("prompt")
    p_prompt.add_argument("text", help="Natural language prompt for ADA")
    p_backup = sub.add_parser("backup", help="Create a consistent backup of ADA memory")
    p_backup.add_argument("--path", required=True)
    sub.add_parser("doctor", help="Check local model and integration readiness")
    p_models = sub.add_parser("models", help="Inspect or explicitly pull configured Ollama models")
    p_models.add_argument("--pull", action="store_true")
    p_gmail = sub.add_parser("auth-gmail", help="Run the explicit Gmail OAuth flow")
    p_gmail.add_argument("--scope", action="append", help="OAuth scope; can be repeated")
    sub.add_parser("setup-instagram", help="Create the private Puppeteer browser profile directory")
    p_finetune = sub.add_parser("finetune", help="Prepare, validate or explicitly train a local LoRA adapter")
    p_finetune.add_argument("action", choices=("prepare", "validate", "train"))
    p_finetune.add_argument("--input", required=True)
    p_finetune.add_argument("--output", required=True)
    p_finetune.add_argument("--model")
    p_finetune.add_argument("--steps", type=int, default=100)

    args = parser.parse_args()
    cfg = load_config()
    print(f"Starting {cfg.get('name', 'ADA')}")
    if args.cmd == "doctor":
        print(json.dumps(diagnose(cfg), indent=2, ensure_ascii=False))
        return
    if args.cmd == "models":
        if not args.pull:
            print(json.dumps(diagnose(cfg)["checks"]["ollama"], indent=2, ensure_ascii=False))
        else:
            print(json.dumps(pull_models(cfg), indent=2, ensure_ascii=False))
        return
    if args.cmd == "auth-gmail":
        print(json.dumps(authenticate(cfg, scopes=args.scope), indent=2, ensure_ascii=False))
        return
    if args.cmd == "setup-instagram":
        print(json.dumps(prepare_instagram_profile(cfg), indent=2, ensure_ascii=False))
        return
    if args.cmd == "finetune":
        if args.action == "prepare":
            print(json.dumps(prepare_dataset(args.input, args.output), indent=2, ensure_ascii=False))
        elif args.action == "validate":
            print(json.dumps(validate_dataset(args.input), indent=2, ensure_ascii=False))
        else:
            if not args.model:
                raise SystemExit("--model es obligatorio para entrenar")
            print(json.dumps(train_lora(args.input, args.model, args.output, args.steps), indent=2, ensure_ascii=False))
        return
    if args.cmd == "serve":
        if args.debug:
            started_at = datetime.now().strftime("%Y%m%d-%H%M%S")
            log_dir = PROJECT_ROOT / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / f"ada-debug-{started_at}.log"
            formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
            stream = logging.StreamHandler()
            stream.setFormatter(formatter)
            file_handler = logging.FileHandler(log_path, encoding="utf-8")
            file_handler.setFormatter(formatter)
            logging.basicConfig(level=logging.DEBUG, handlers=[stream, file_handler], force=True)
            print(f"Debug log: {log_path}")
        else:
            logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(name)s: %(message)s")
        if args.asgi or os.environ.get("ADA_WEB_FRAMEWORK") == "asgi" or cfg.get("web_framework") == "asgi":
            try:
                import uvicorn
            except ImportError as exc:
                raise SystemExit("Instalá la extra web: python3 -m pip install -e '.[web]'") from exc
            uvicorn.run(
                "ada.interfaces.web.asgi:create_app",
                factory=True,
                host=os.environ.get("ADA_UI_HOST", "127.0.0.1"),
                port=int(os.environ.get("ADA_UI_PORT", "5006")),
            )
        else:
            from ada.interfaces.web.server import main as serve_web

            serve_web()
        return
    default_db = str(Path.home() / "Desktop" / "ADA_Data" / "memory.db")
    mem = Memory(cfg.get("db_path", default_db))
    if args.cmd == "index":
        index_folder(args.dir, mem)
    elif args.cmd == "suggest":
        suggest_organization(args.dir, mem)
    elif args.cmd == "run":
        # start interactive agent loop
        agent = Agent(cfg)
        agent.interactive_loop()
    elif args.cmd == "prompt":
        text = args.text.strip()
        # simple heuristics: detect index or suggest commands in natural language
        lowered = text.lower()
        if lowered.startswith("index") or "index" in lowered or "scan" in lowered:
            # try to extract a path
            parts = text.split()
            path = None
            for p in parts:
                if p.startswith("/") or p.startswith("~") or p.startswith("."):
                    path = os.path.expanduser(p)
                    break
            if path:
                print("Heuristic: calling index on", path)
                mem = Memory(cfg.get("db_path", default_db))
                index_folder(path, mem)
                return
        if "suggest" in lowered or "organize" in lowered or "orden" in lowered:
            parts = text.split()
            path = None
            for p in parts:
                if p.startswith("/") or p.startswith("~") or p.startswith("."):
                    path = os.path.expanduser(p)
                    break
            if path:
                print("Heuristic: calling suggest on", path)
                mem = Memory(cfg.get("db_path", default_db))
                suggest_organization(path, mem)
                return
        # Otherwise, use the agent parser to interpret the prompt.
        agent = Agent(cfg)
        parsed = agent.parse_prompt(text)
        action = parsed.get("action")
        if action == "organize":
            path = parsed.get("path") or None
            if not path:
                # try simple extraction from quotes
                import re

                m = re.search(r'"([^"]+)"', text)
                if m:
                    candidate = m.group(1)
                    if candidate.startswith("/") or candidate.startswith("~") or candidate.startswith("."):
                        path = os.path.expanduser(candidate)
            if not path:
                print("Could not find a path to organize; please specify a directory.")
            else:
                confirm = input(f"Esto moverá archivos en {path}. ¿Confirmás? [s/N] ").lower().strip() in (
                    "s",
                    "si",
                    "sí",
                    "y",
                    "yes",
                )
                print(
                    agent.decide_and_run(
                        {"type": "organize_photos", "payload": {"dir": path}, "confirm": confirm, "complexity": 4}
                    )
                )
            return
        if action == "index":
            path = parsed.get("path")
            if path:
                mem = Memory(default_db)
                index_folder(path, mem)
            else:
                print("No path detected for indexing")
            return
        if action == "suggest":
            path = parsed.get("path")
            if path:
                mem = Memory(default_db)
                suggest_organization(path, mem)
            else:
                print("No path detected for suggest")
            return
        if action == "run":
            cmd = parsed.get("command")
            if cmd:
                confirm = input(f"¿Confirmás ejecutar '{cmd}'? [s/N] ").lower().strip() in ("s", "si", "sí", "y", "yes")
                print(
                    agent.decide_and_run(
                        {"type": "run_script", "payload": {"command": cmd}, "confirm": confirm, "complexity": 2}
                    )
                )
                return
            print("No command found to run")
            return
        # fallback: send as general prompt to agent
        task = {"type": None, "prompt": text, "complexity": parsed.get("complexity", 5)}
        res = agent.decide_and_run(task)
        print(res)
    elif args.cmd == "backup":
        print(mem.backup_to(args.path))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
