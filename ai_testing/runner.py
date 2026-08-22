"""Run safe prompt cases against ADA and write auditable results.

Only prompts from the catalog are accepted. Cases containing mutation verbs or
shell-like commands are rejected before any request is sent.
"""
from __future__ import annotations
import argparse, json, re, sqlite3, subprocess, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_RESULTS = ROOT / "results.json"
DEFAULT_DB = Path.home() / "Desktop" / "ADA_Data" / "ai_testing.db"
FORBIDDEN = re.compile(r"\b(borr[aá]|elimin[aá]|mov[eé]|renombr[aá]|escrib[ií]|cre[aá]|sub[ií]|descarg[aá]|ejecut[aá]|matar|kill|rm|delete|move|write|upload)\b", re.I)

def safe_case(case):
    return not FORBIDDEN.search(str(case.get("prompt", ""))) and not re.search(r"(^|\s)(sudo|rm\s+-|python\s+-c|bash\s+-c)\b", str(case.get("prompt", "")), re.I)

def request_ada(url, prompt, session):
    payload = json.dumps({"message": prompt, "lang": "es", "source": "ai_testing", "session_id": session}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type":"application/json"}, method="POST")
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=600) as response:
            body = json.loads(response.read().decode())
        return body, time.monotonic() - started, None
    except Exception as exc:
        return {}, time.monotonic() - started, str(exc)

def evaluate(case, body, elapsed, error=None):
    reply = str(body.get("reply") or body.get("message") or "")
    low = reply.casefold()
    missing = [term for term in case.get("must_contain", []) if term.casefold() not in low]
    missing_matches = [pattern for pattern in case.get("must_match", []) if not re.search(pattern, reply, re.I)]
    criteria_total = len(case.get("must_contain", [])) + len(case.get("must_match", []))
    missing_all = missing + [f"patrón: {pattern}" for pattern in missing_matches]
    failed = bool(error or body.get("error") or not reply or missing_all or elapsed > float(case.get("max_seconds", 600)))
    score = 1 - len(missing_all) / max(1, criteria_total) - (0.25 if error else 0)
    return {"passed": not failed, "score": max(0, round(score, 3)), "missing": missing_all, "reply_chars": len(reply), "elapsed_seconds": round(elapsed, 3), "error": error or body.get("error")}

def llm_judge(case, reply, endpoint="http://127.0.0.1:11434/api/generate", model="qwen3:8b"):
    prompt = ("Evaluá esta respuesta de ADA. Devolvé SOLO JSON con score (0 a 1), passed (boolean), "
              "issues (lista breve) y rationale. No propongas acciones ni ejecutes herramientas.\n"
              f"Pedido: {case['prompt']}\nRespuesta: {reply}")
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False, "format": "json", "options": {"temperature": 0}}).encode()
    req = urllib.request.Request(endpoint, data=payload, headers={"Content-Type":"application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as response: return json.loads(json.loads(response.read().decode()).get("response", "{}"))
    except Exception as exc: return {"error": str(exc)}

def init_db(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE IF NOT EXISTS runs (run_id TEXT, commit_id TEXT, case_id TEXT, prompt TEXT, response TEXT, evaluation TEXT, created_at REAL)")
    columns = {row[1] for row in conn.execute("PRAGMA table_info(runs)")}
    if "commit_id" not in columns:
        conn.execute("ALTER TABLE runs ADD COLUMN commit_id TEXT")
    conn.commit()
    return conn

def commit_id():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT.parent, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unknown"

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--url", default="http://127.0.0.1:5005/api/chat"); ap.add_argument("--catalog", default=str(ROOT / "prompts.json")); ap.add_argument("--results", default=str(DEFAULT_RESULTS)); ap.add_argument("--db", default=str(DEFAULT_DB)); ap.add_argument("--case"); ap.add_argument("--judge", action="store_true", help="usar un modelo local independiente para evaluar cada respuesta"); args = ap.parse_args()
    cases = json.loads(Path(args.catalog).read_text(encoding="utf-8")); cases = [c for c in cases if not args.case or c["id"] == args.case]
    unsafe = [c["id"] for c in cases if not safe_case(c)]
    if unsafe: raise SystemExit(f"Casos bloqueados por seguridad: {', '.join(unsafe)}")
    run_id = time.strftime("%Y%m%d-%H%M%S"); revision = commit_id(); summary=[]; conn = init_db(Path(args.db))
    for case in cases:
        body, elapsed, error = request_ada(args.url, case["prompt"], f"ai_testing_{run_id}_{case['id']}")
        evaluation = evaluate(case, body, elapsed, error)
        if args.judge and body.get("reply"): evaluation["llm_judge"] = llm_judge(case, body["reply"])
        summary.append({"id":case["id"], **evaluation})
        conn.execute("INSERT INTO runs (run_id, commit_id, case_id, prompt, response, evaluation, created_at) VALUES (?,?,?,?,?,?,?)", (run_id, revision, case["id"], case["prompt"], json.dumps(body, ensure_ascii=False), json.dumps(evaluation, ensure_ascii=False), time.time())); conn.commit()
        print(json.dumps({"id":case["id"], **evaluation}, ensure_ascii=False))
    aggregate = {
        "total": len(summary), "passed": sum(x["passed"] for x in summary),
        "failed": sum(not x["passed"] for x in summary),
        "pass_rate": round(sum(x["passed"] for x in summary) / max(1, len(summary)), 3),
        "avg_latency_seconds": round(sum(x["elapsed_seconds"] for x in summary) / max(1, len(summary)), 3),
        "max_latency_seconds": max((x["elapsed_seconds"] for x in summary), default=0),
    }
    conn.close(); result = {"run_id": run_id, "commit_id": revision, "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "metrics": aggregate, "cases": summary}
    target = Path(args.results); target.parent.mkdir(parents=True, exist_ok=True); temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"); temporary.replace(target)
    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__": main()
