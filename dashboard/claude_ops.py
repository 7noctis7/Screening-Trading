#!/usr/bin/env python3
"""Claude Ops — a clickable control room for Claude Code, wired to Obsidian.

Zero dependencies (Python 3.10+ stdlib). Run from your project root:

    python3 dashboard/claude_ops.py            # http://localhost:8787

Reads:  ~/.claude/projects/<slug>/*.jsonl   (session transcripts)
        .claude/ops/friction.jsonl          (hook-collected failures)
        vault/                              (Obsidian memory)
Runs:   one-click skills via `claude -p "/skill" ...` (headless)

Env overrides: OPS_PROJECT_DIR, OPS_VAULT_DIR, OPS_PORT, OPS_CLAUDE_BIN,
               OPS_PERMISSION_MODE (default: acceptEdits — set to `plan`
               for read-only dry runs).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PROJECT_DIR = Path(os.environ.get("OPS_PROJECT_DIR", os.getcwd())).resolve()
VAULT_DIR = Path(os.environ.get("OPS_VAULT_DIR", PROJECT_DIR / "vault"))
PORT = int(os.environ.get("OPS_PORT", "8787"))
CLAUDE_BIN = os.environ.get("OPS_CLAUDE_BIN", "claude")
PERM_MODE = os.environ.get("OPS_PERMISSION_MODE", "acceptEdits")
MAX_SESSIONS = 60

SKILLS = [
    ("session-open", "Open session", "Vault ritual: state synthesis + P0 plan"),
    ("session-close", "Close session", "Journal, TODO, ADR, diagrams, Notion"),
    ("audit-sessions", "Audit sessions", "Sub-agents cluster friction, propose fixes"),
    ("backtest-review", "Backtest review", "quant-critic verdict + vault record"),
    ("vault-sync", "Vault ⇄ Notion sync", "Drift check + push pilotage to Notion"),
]

CORRECTION_RE = re.compile(
    r"\b(no|nope|wrong|stop|don'?t|not what|revert|undo|why did|again|"
    r"non|pas ça|refais|arrête|encore|faux)\b", re.I)

FRICTION_RULES = [
    ("permissions", r"permission|denied|not allowed|blocked by|approval"),
    ("tests failing", r"pytest|assert|test.*fail|failed.*test|FAILED"),
    ("deps & env", r"modulenotfound|importerror|no module|pip |uv |version conflict|command not found"),
    ("types & lint", r"mypy|ruff|type error|annotation|lint"),
    ("data & APIs", r"rate limit|429|timeout|connection|http|api key|quota|yfinance|ccxt|fred|alpaca|finnhub"),
    ("db & migrations", r"alembic|sqlalchemy|duckdb|parquet|schema|migration"),
    ("git", r"git |merge|conflict|rebase|commit"),
    ("paths & files", r"no such file|not found|enoent|filenotfound|directory"),
    ("rule violations", r"400 lines|project rule|look-ahead|leak"),
]


def classify(text: str) -> str:
    t = (text or "").lower()
    for name, pat in FRICTION_RULES:
        if re.search(pat, t):
            return name
    return "other"


def _text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return ""


def _parse_ts(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def find_session_dirs() -> list[Path]:
    root = Path.home() / ".claude" / "projects"
    if not root.is_dir():
        return []
    slug = str(PROJECT_DIR).replace("/", "-").replace(".", "-")
    exact = root / slug
    if exact.is_dir():
        return [exact]
    base = PROJECT_DIR.name.lower()
    hits = [d for d in root.iterdir() if d.is_dir() and base in d.name.lower()]
    return hits or sorted(root.iterdir(), key=lambda d: d.stat().st_mtime, reverse=True)[:3]


def parse_session(fp: Path) -> dict:
    s = {"file": fp.name, "start": None, "end": None, "messages": 0, "tool_calls": 0,
         "errors": 0, "corrections": 0, "tools": {}, "friction": {}, "samples": []}
    try:
        with fp.open(errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                ts = _parse_ts(rec.get("timestamp"))
                if ts:
                    s["start"] = s["start"] or ts
                    s["end"] = ts
                msg = rec.get("message") or {}
                content = msg.get("content")
                rtype = rec.get("type")
                if rtype in ("user", "assistant"):
                    s["messages"] += 1
                if rtype == "assistant" and isinstance(content, list):
                    for b in content:
                        if isinstance(b, dict) and b.get("type") == "tool_use":
                            s["tool_calls"] += 1
                            name = b.get("name", "?")
                            s["tools"].setdefault(name, [0, 0])[0] += 1
                if rtype == "user":
                    if isinstance(content, list):
                        for b in content:
                            if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("is_error"):
                                s["errors"] += 1
                                err = _text_of(b.get("content"))[:300]
                                cat = classify(err)
                                s["friction"][cat] = s["friction"].get(cat, 0) + 1
                                if len(s["samples"]) < 3:
                                    s["samples"].append(err[:160])
                                tu = rec.get("toolUseResult") or {}
                                tname = tu.get("toolName") or "?"
                                s["tools"].setdefault(tname, [0, 0])[1] += 1
                    text = _text_of(content)
                    if text and not text.startswith(("<command", "Caveat:")) and CORRECTION_RE.search(text):
                        s["corrections"] += 1
    except Exception:
        pass
    if s["start"] and s["end"]:
        s["duration_min"] = round((s["end"] - s["start"]).total_seconds() / 60, 1)
    else:
        s["duration_min"] = 0
    s["start"] = s["start"].isoformat() if s["start"] else None
    s["end"] = s["end"].isoformat() if s["end"] else None
    return s


def load_friction_hook_log() -> list[dict]:
    fp = PROJECT_DIR / ".claude" / "ops" / "friction.jsonl"
    out = []
    if fp.exists():
        for line in fp.read_text(errors="ignore").splitlines()[-500:]:
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def vault_status() -> dict:
    v = {"present": VAULT_DIR.is_dir(), "path": str(VAULT_DIR), "p0": 0, "p1": 0,
         "journal_age_days": None, "diagrams_ok": False, "files": 0}
    if not v["present"]:
        return v
    v["files"] = sum(1 for _ in VAULT_DIR.rglob("*.md"))
    todo = VAULT_DIR / "03_TODO.md"
    if todo.exists():
        t = todo.read_text(errors="ignore")
        v["p0"], v["p1"] = len(re.findall(r"\bP0\b", t)), len(re.findall(r"\bP1\b", t))
    journal = VAULT_DIR / "04_JOURNAL.md"
    if journal.exists():
        v["journal_age_days"] = round((time.time() - journal.stat().st_mtime) / 86400, 1)
    arch = VAULT_DIR / "01_ARCHITECTURE.md"
    if arch.exists():
        v["diagrams_ok"] = arch.read_text(errors="ignore").count("```mermaid") >= 2
    return v


def build_state() -> dict:
    files = []
    for d in find_session_dirs():
        files += list(d.glob("*.jsonl"))
    files = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)[:MAX_SESSIONS]
    sessions = [parse_session(fp) for fp in files]
    agg_friction, agg_tools = {}, {}
    for s in sessions:
        for k, n in s["friction"].items():
            agg_friction[k] = agg_friction.get(k, 0) + n
        for t, (calls, errs) in s["tools"].items():
            a = agg_tools.setdefault(t, [0, 0])
            a[0] += calls
            a[1] += errs
    for ev in load_friction_hook_log():
        if ev.get("event") == "tool_failure":
            cat = classify(ev.get("error", ""))
            agg_friction[cat] = agg_friction.get(cat, 0) + 1
    total_calls = sum(v[0] for v in agg_tools.values()) or 1
    total_errs = sum(v[1] for v in agg_tools.values())
    return {
        "project": str(PROJECT_DIR), "generated": datetime.now(timezone.utc).isoformat(),
        "sessions": sessions,
        "totals": {
            "sessions": len(sessions),
            "hours": round(sum(s["duration_min"] for s in sessions) / 60, 1),
            "tool_calls": total_calls, "errors": total_errs,
            "error_rate": round(100 * total_errs / total_calls, 1),
            "corrections": sum(s["corrections"] for s in sessions),
        },
        "friction": sorted(agg_friction.items(), key=lambda kv: -kv[1]),
        "tools": sorted(([t, c, e] for t, (c, e) in agg_tools.items()), key=lambda x: -x[2]),
        "vault": vault_status(),
        "skills": [{"id": i, "label": l, "hint": h} for i, l, h in SKILLS],
        "perm_mode": PERM_MODE,
    }


JOBS: dict[str, dict] = {}


def run_skill(job_id: str, skill: str) -> None:
    job = JOBS[job_id]
    cmd = [CLAUDE_BIN, "-p", f"/{skill}", "--permission-mode", PERM_MODE]
    job["cmd"] = " ".join(cmd)
    try:
        proc = subprocess.Popen(cmd, cwd=PROJECT_DIR, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, bufsize=1)
        job["status"] = "running"
        for line in proc.stdout:
            job["log"].append(line.rstrip())
            job["log"] = job["log"][-400:]
        proc.wait()
        job["status"] = "done" if proc.returncode == 0 else f"exit {proc.returncode}"
    except FileNotFoundError:
        job["status"] = "error"
        job["log"].append(f"`{CLAUDE_BIN}` not found — set OPS_CLAUDE_BIN.")
    except Exception as e:  # noqa: BLE001
        job["status"] = "error"
        job["log"].append(str(e))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # silence default logging
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            self._send(200, PAGE.encode(), "text/html; charset=utf-8")
        elif self.path == "/api/state":
            self._send(200, json.dumps(build_state(), default=str).encode(), "application/json")
        elif self.path == "/api/jobs":
            self._send(200, json.dumps(JOBS).encode(), "application/json")
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self):
        if self.path != "/api/run":
            return self._send(404, b"", "text/plain")
        n = int(self.headers.get("Content-Length", 0))
        skill = json.loads(self.rfile.read(n) or b"{}").get("skill", "")
        if skill not in {s[0] for s in SKILLS}:
            return self._send(400, b'{"error":"unknown skill"}', "application/json")
        job_id = uuid.uuid4().hex[:8]
        JOBS[job_id] = {"skill": skill, "status": "starting", "log": [],
                        "started": datetime.now().strftime("%H:%M:%S")}
        threading.Thread(target=run_skill, args=(job_id, skill), daemon=True).start()
        self._send(200, json.dumps({"job": job_id}).encode(), "application/json")


PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Claude Ops — quant desk</title>
<style>
:root{--bg:#141922;--panel:#1B2230;--line:#2A3446;--ink:#E9EDF4;--dim:#8B97AB;
--accent:#E8A33D;--good:#3FBF7F;--bad:#E06060;--mono:'IBM Plex Mono',ui-monospace,Menlo,monospace;
--sans:'Spline Sans',system-ui,-apple-system,sans-serif}
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Spline+Sans:wght@400;500;700&display=swap');
*{box-sizing:border-box;margin:0}body{background:var(--bg);color:var(--ink);font:15px/1.5 var(--sans);padding:28px 32px 80px}
h1{font-size:20px;font-weight:700;letter-spacing:.3px}h1 span{color:var(--accent)}
.sub{color:var(--dim);font-family:var(--mono);font-size:12px;margin:4px 0 22px}
.grid{display:grid;gap:14px}.cols5{grid-template-columns:repeat(5,1fr)}.cols2{grid-template-columns:3fr 2fr}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px 18px}
.kpi b{display:block;font:600 26px var(--mono)}.kpi small{color:var(--dim);text-transform:uppercase;letter-spacing:.08em;font-size:10px}
.kpi .warn{color:var(--bad)}.kpi .ok{color:var(--good)}
h2{font-size:12px;color:var(--dim);text-transform:uppercase;letter-spacing:.1em;margin-bottom:12px}
#spectrum{display:flex;height:34px;border-radius:6px;overflow:hidden;border:1px solid var(--line)}
#spectrum div{min-width:4px}.legend{display:flex;flex-wrap:wrap;gap:10px 18px;margin-top:10px;font-family:var(--mono);font-size:12px;color:var(--dim)}
.legend i{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:6px}
table{width:100%;border-collapse:collapse;font-family:var(--mono);font-size:12.5px}
th{text-align:left;color:var(--dim);font-weight:400;padding:4px 8px;border-bottom:1px solid var(--line)}
td{padding:5px 8px;border-bottom:1px solid var(--line)}tr:last-child td{border:0}
.err{color:var(--bad)}.mut{color:var(--dim)}
.skills{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:12px}
button.skill{background:var(--bg);border:1px solid var(--line);border-radius:10px;color:var(--ink);
padding:14px;text-align:left;cursor:pointer;font:inherit;transition:border-color .15s}
button.skill:hover{border-color:var(--accent)}button.skill b{display:block;font-size:14px}
button.skill small{color:var(--dim);font-size:11.5px}
#log{background:#0F131B;border:1px solid var(--line);border-radius:10px;padding:14px;margin-top:14px;
font:12px/1.6 var(--mono);max-height:280px;overflow:auto;white-space:pre-wrap;color:#B9C4D6}
.badge{font:600 11px var(--mono);padding:2px 8px;border-radius:20px;border:1px solid var(--line)}
.badge.run{color:var(--accent);border-color:var(--accent)}.badge.done{color:var(--good)}
@media(max-width:1000px){.cols5{grid-template-columns:repeat(2,1fr)}.cols2{grid-template-columns:1fr}}
</style></head><body>
<h1>CLAUDE <span>OPS</span> · screening &amp; trading system</h1>
<div class="sub" id="meta">loading…</div>
<div class="grid cols5" id="kpis"></div>
<div class="card" style="margin-top:14px"><h2>Friction spectrum — where sessions bleed time</h2>
<div id="spectrum"></div><div class="legend" id="legend"></div></div>
<div class="grid cols2" style="margin-top:14px">
<div class="card"><h2>Sessions (most recent first)</h2><div style="max-height:340px;overflow:auto"><table id="sessions"></table></div></div>
<div class="card"><h2>Errors by tool · vault health</h2><table id="tools"></table><div id="vault" style="margin-top:14px;font-family:var(--mono);font-size:12.5px"></div></div>
</div>
<div class="card" style="margin-top:14px"><h2>One-click skills <span class="mut" id="perm"></span></h2>
<div class="skills" id="skills"></div><div id="log">Skill output will stream here.</div></div>
<script>
const COLORS=['#E8A33D','#5B8DEF','#3FBF7F','#E06060','#B07CE8','#4FC3C8','#D0A0A0','#8B97AB','#C9C05A','#6C7A93'];
const $=id=>document.getElementById(id);
async function load(){
 const st=await (await fetch('/api/state')).json();
 $('meta').textContent=st.project+' · '+st.totals.sessions+' sessions parsed · generated '+st.generated.slice(0,19)+'Z';
 const t=st.totals;
 $('kpis').innerHTML=[['Sessions',t.sessions,''],['Hours in session',t.hours,''],
  ['Tool calls',t.tool_calls,''],['Tool error rate',t.error_rate+'%',t.error_rate>8?'warn':'ok'],
  ['User corrections',t.corrections,t.corrections>t.sessions?'warn':'']]
  .map(([l,v,c])=>`<div class="card kpi"><b class="${c}">${v}</b><small>${l}</small></div>`).join('');
 const total=st.friction.reduce((a,[,n])=>a+n,0)||1;
 $('spectrum').innerHTML=st.friction.map(([k,n],i)=>`<div title="${k}: ${n}" style="width:${100*n/total}%;background:${COLORS[i%10]}"></div>`).join('')||'<div style="width:100%;background:var(--line)"></div>';
 $('legend').innerHTML=st.friction.map(([k,n],i)=>`<span><i style="background:${COLORS[i%10]}"></i>${k} · ${n}</span>`).join('')||'no friction recorded yet';
 $('sessions').innerHTML='<tr><th>date</th><th>min</th><th>msgs</th><th>tools</th><th>errs</th><th>corr.</th><th>top friction</th></tr>'+
  st.sessions.map(s=>{const top=Object.entries(s.friction).sort((a,b)=>b[1]-a[1])[0];
   return `<tr><td>${(s.start||'?').slice(0,16)}</td><td>${s.duration_min}</td><td>${s.messages}</td><td>${s.tool_calls}</td><td class="${s.errors?'err':''}">${s.errors}</td><td>${s.corrections}</td><td class="mut">${top?top[0]:''}</td></tr>`}).join('');
 $('tools').innerHTML='<tr><th>tool</th><th>calls</th><th>errors</th><th>rate</th></tr>'+
  st.tools.slice(0,8).map(([t,c,e])=>`<tr><td>${t}</td><td>${c}</td><td class="${e?'err':''}">${e}</td><td>${c?(100*e/c).toFixed(1):0}%</td></tr>`).join('');
 const v=st.vault;
 $('vault').innerHTML=v.present?`vault: ${v.files} notes · <b style="color:${v.p0?'var(--bad)':'var(--good)'}">P0: ${v.p0}</b> · P1: ${v.p1}<br>journal age: ${v.journal_age_days}d · diagrams (2× mermaid): <b style="color:${v.diagrams_ok?'var(--good)':'var(--bad)'}">${v.diagrams_ok?'OK':'MISSING'}</b>`:`vault not found at ${v.path} — set OPS_VAULT_DIR`;
 $('perm').textContent=' · permission mode: '+st.perm_mode;
 $('skills').innerHTML=st.skills.map(s=>`<button class="skill" onclick="run('${s.id}')"><b>/${s.id}</b><small>${s.hint}</small></button>`).join('');
}
async function run(skill){
 $('log').textContent='▶ launching /'+skill+' …';
 const {job}=await (await fetch('/api/run',{method:'POST',body:JSON.stringify({skill})})).json();
 const poll=setInterval(async()=>{
  const jobs=await (await fetch('/api/jobs')).json();const j=jobs[job];if(!j)return;
  $('log').textContent='['+j.status+'] '+j.cmd+'\n\n'+j.log.join('\n');
  $('log').scrollTop=$('log').scrollHeight;
  if(j.status!=='running'&&j.status!=='starting'){clearInterval(poll);load();}
 },1200);
}
load();setInterval(load,30000);
</script></body></html>"""


if __name__ == "__main__":
    print(f"Claude Ops → http://localhost:{PORT}  (project: {PROJECT_DIR})")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
