#!/usr/bin/env python3
import argparse
import logging
from datetime import datetime
from pathlib import Path
import os

from src.ada.infrastructure.persistence.sqlite import Memory
from src.ada.application.indexer import index_folder, suggest_organization
from src.ada.application.agent import Agent
from src.ada.config import load_config as load_validated_config

PROJECT_ROOT = Path(__file__).resolve().parents[4]

def load_config():
    cfg_path = PROJECT_ROOT / 'config.json'
    try:
        return load_validated_config(cfg_path, PROJECT_ROOT)
    except (OSError, ValueError) as exc:
        logging.getLogger('ada.cli').warning('config_load_failed path=%s error=%s', cfg_path, exc)
        return {"name": "ADA", "max_threads": 4, "use_mps": False, "db_path": str(PROJECT_ROOT / 'memory.db')}

def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='cmd')
    p_index = sub.add_parser('index')
    p_index.add_argument('--dir', required=True)
    p_suggest = sub.add_parser('suggest')
    p_suggest.add_argument('--dir', required=True)
    p_run = sub.add_parser('run')
    p_serve = sub.add_parser('serve', help='Start the web UI and ADA agent in one process')
    p_serve.add_argument('-debug', '--debug', action='store_true', help='Enable detailed router and model logs')
    p_prompt = sub.add_parser('prompt')
    p_prompt.add_argument('text', help='Natural language prompt for ADA')

    args = parser.parse_args()
    cfg = load_config()
    print(f"Starting {cfg.get('name', 'ADA')}")
    if args.cmd == 'serve':
        if args.debug:
            started_at = datetime.now().strftime('%Y%m%d-%H%M%S')
            log_dir = PROJECT_ROOT / 'logs'
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / f'ada-debug-{started_at}.log'
            formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
            stream = logging.StreamHandler()
            stream.setFormatter(formatter)
            file_handler = logging.FileHandler(log_path, encoding='utf-8')
            file_handler.setFormatter(formatter)
            logging.basicConfig(level=logging.DEBUG, handlers=[stream, file_handler], force=True)
            print(f'Debug log: {log_path}')
        else:
            logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(name)s: %(message)s')
        from src.ada.interfaces.web.server import main as serve_web
        serve_web()
        return
    mem = Memory(cfg.get('db_path', str(Path(__file__).parent / 'memory.db')))
    if args.cmd == 'index':
        index_folder(args.dir, mem)
    elif args.cmd == 'suggest':
        suggest_organization(args.dir, mem)
    elif args.cmd == 'run':
        # start interactive agent loop
        agent = Agent(cfg)
        agent.interactive_loop()
    elif args.cmd == 'prompt':
        text = args.text.strip()
        # simple heuristics: detect index or suggest commands in natural language
        lowered = text.lower()
        if lowered.startswith('index') or 'index' in lowered or 'scan' in lowered:
            # try to extract a path
            parts = text.split()
            path = None
            for p in parts:
                if p.startswith('/') or p.startswith('~') or p.startswith('.'): 
                    path = os.path.expanduser(p)
                    break
            if path:
                print('Heuristic: calling index on', path)
                mem = Memory(cfg.get('db_path', str(Path(__file__).parent / 'memory.db')))
                index_folder(path, mem)
                return
        if 'suggest' in lowered or 'organize' in lowered or 'orden' in lowered:
            parts = text.split()
            path = None
            for p in parts:
                if p.startswith('/') or p.startswith('~') or p.startswith('.'):
                    path = os.path.expanduser(p)
                    break
            if path:
                print('Heuristic: calling suggest on', path)
                mem = Memory(cfg.get('db_path', str(Path(__file__).parent / 'memory.db')))
                suggest_organization(path, mem)
                return
        # Otherwise, use the agent parser to interpret the prompt.
        agent = Agent(cfg)
        parsed = agent.parse_prompt(text)
        action = parsed.get('action')
        if action == 'organize':
            path = parsed.get('path') or None
            if not path:
                # try simple extraction from quotes
                import re
                m = re.search(r'"([^"]+)"', text)
                if m:
                    candidate = m.group(1)
                    if candidate.startswith('/') or candidate.startswith('~') or candidate.startswith('.'):
                        path = os.path.expanduser(candidate)
            if not path:
                print('Could not find a path to organize; please specify a directory.')
            else:
                confirm = input(f"Esto moverá archivos en {path}. ¿Confirmás? [s/N] ").lower().strip() in ('s', 'si', 'sí', 'y', 'yes')
                print(agent.decide_and_run({'type': 'organize_photos', 'payload': {'dir': path}, 'confirm': confirm, 'complexity': 4}))
            return
        if action == 'index':
            path = parsed.get('path')
            if path:
                mem = Memory(cfg.get('db_path', str(Path(__file__).parent / 'memory.db')))
                index_folder(path, mem)
            else:
                print('No path detected for indexing')
            return
        if action == 'suggest':
            path = parsed.get('path')
            if path:
                mem = Memory(cfg.get('db_path', str(Path(__file__).parent / 'memory.db')))
                suggest_organization(path, mem)
            else:
                print('No path detected for suggest')
            return
        if action == 'run':
            cmd = parsed.get('command')
            if cmd:
                confirm = input(f"¿Confirmás ejecutar '{cmd}'? [s/N] ").lower().strip() in ('s', 'si', 'sí', 'y', 'yes')
                print(agent.decide_and_run({'type': 'run_script', 'payload': {'command': cmd}, 'confirm': confirm, 'complexity': 2}))
                return
            print('No command found to run')
            return
        # fallback: send as general prompt to agent
        task = {'type': None, 'prompt': text, 'complexity': parsed.get('complexity', 5)}
        res = agent.decide_and_run(task)
        print(res)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
