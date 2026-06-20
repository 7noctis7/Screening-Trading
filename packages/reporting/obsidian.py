"""Quant Obsidian Vault — pont backend → coffre Obsidian (graphe de connaissances).

Transforme la sortie du terminal en notes Markdown **idempotentes**, sémantiques (front matter YAML +
liens `[[...]]`), exploitables par l'IA et le plugin Dataview. Premiers principes :

  • Écriture ATOMIQUE (`os.replace`) → jamais de coffre corrompu, même en cas d'interruption.
  • ISOLATION : toute erreur disque est avalée et journalisée — `sync_obsidian_vault()` ne LÈVE JAMAIS,
    afin que la génération de rapports ne puisse PAS bloquer le trading live (exigence Citadel).
  • IDEMPOTENT : régénérer un même jour réécrit proprement la note, sans doublon.
  • PUR/TESTABLE : la construction du Markdown est séparée des E/S disque.

──────────────────────────────────────────────────────────────────────────────
SCHÉMA DES MÉTADONNÉES (front matter YAML) — pour requêtes Dataview / agent IA :

  ---
  type: daily_journal | incident | attribution_hub
  date: 2026-06-20                # ISO
  regime_cycle: slowdown          # cycle macro
  regime_risk: risk_off           # risk_on | neutral | risk_off
  vix: 18.4
  sharpe: 0.89
  sortino: 0.84
  max_drawdown: -0.306            # négatif
  var_95: 0.021                   # VaR 95 % (positif = perte)
  cvar_95: 0.034
  garch_vol: 0.18                 # vol prévue GARCH(1,1) annualisée
  alpha_annual: 0.052             # alpha CAPM net de frais vs cœur QQQ
  beta_qqq: 0.93
  kill_switch: false              # true si drawdown < seuil de coupe
  risk_limits_ok: true            # false si ≥1 limite franchie
  n_breaches: 0
  tags: [quant, journal]
  ---

Requête Dataview type (dans n'importe quelle note) :
  ```dataview
  table sharpe, max_drawdown, var_95, kill_switch from #journal sort date desc
  ```
──────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import logging
import math
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger("quant.obsidian")

_ROOT = Path(__file__).resolve().parents[2]
_VAULT = _ROOT / "vault"
_JOURNAL_DIR = "03_Journal"
_POSTMORTEM_DIR = "04_Post_Mortem"
_ASSETS_DIR = "_assets"
_REGIMES_DIR = "05_Regimes"
_HUB_NOTE = "Preset_Performance.md"

# Seuil de kill-switch drawdown (surchargeable). -0.30 = coupe si le drawdown dépasse -30 %.
_KILL_DD = float(os.environ.get("QUANT_KILL_DD", "0.30"))


# ─────────────────────────── E/S bas niveau (robustes) ───────────────────────────
def _atomic_write(path: Path, content: str) -> bool:
    """Écrit un fichier de façon ATOMIQUE. Renvoie True/False, ne lève JAMAIS (isolation trading)."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp, path)
            return True
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
    except Exception as e:  # noqa: BLE001 — un échec disque ne doit pas casser le pipeline
        log.warning("obsidian: écriture échouée %s : %s", path, e)
        return False


# ─────────────────────────── Formatage (pur) ───────────────────────────
def _f(x: Any, nd: int = 2, default: str = "—") -> str:
    try:
        if x is None:
            return default
        return f"{float(x):.{nd}f}"
    except (TypeError, ValueError):
        return default


def _pct(x: Any, nd: int = 1, default: str = "—") -> str:
    try:
        return f"{float(x) * 100:.{nd}f}%"
    except (TypeError, ValueError):
        return default


def _yaml_front_matter(meta: dict[str, Any]) -> str:
    """Sérialise un front matter YAML plat (scalaires + listes de chaînes). Sans dépendance."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, bool):
            lines.append(f"{k}: {'true' if v else 'false'}")
        elif isinstance(v, (int, float)):
            lines.append(f"{k}: {v}")
        elif isinstance(v, (list, tuple)):
            inner = ", ".join(str(x) for x in v)
            lines.append(f"{k}: [{inner}]")
        elif v is None:
            lines.append(f"{k}:")
        else:
            s = str(v).replace("\n", " ")
            lines.append(f"{k}: {s}")
    lines.append("---")
    return "\n".join(lines)


def _svg_sparkline(vals: list[float], w: int = 520, h: int = 90, color: str = "#22c55e") -> str:
    """Sparkline SVG ultra-légère (stdlib) de la courbe d'equity — aucune dépendance graphique."""
    v = [float(x) for x in vals if x is not None]
    if len(v) < 2:
        return ""
    lo, hi = min(v), max(v)
    rng = (hi - lo) or 1.0
    pts = " ".join(f"{i / (len(v) - 1) * w:.1f},{h - (x - lo) / rng * h:.1f}" for i, x in enumerate(v))
    up = v[-1] >= v[0]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
            f'<polyline fill="none" stroke="{color if up else "#f43f5e"}" stroke-width="1.6" '
            f'stroke-linejoin="round" points="{pts}"/></svg>')


# ─────────────────────────── Attribution de performance (pur) ───────────────────────────
def compute_attribution(snapshot: dict) -> dict:
    """Alpha (net de frais) du PRESET vs Beta du cœur QQQ — modèle CAPM (rf=0), sur les courbes réelles.

    alpha_annuel = R̄_preset·252 − beta · R̄_qqq·252  ·  beta = cov(preset, qqq) / var(qqq).
    """
    cur = snapshot.get("index_core_curves", {}) or {}
    preset, qqq = cur.get("preset") or [], cur.get("qqq") or []
    n = min(len(preset), len(qqq))
    out: dict[str, Any] = {"available": False}
    if n < 30:
        return out
    pr = [preset[i] / preset[i - 1] - 1 for i in range(n - len(preset) + 1, n) if preset[i - 1]]
    # alignement strict sur la fenêtre commune
    p = preset[-n:]; q = qqq[-n:]
    rp = [p[i] / p[i - 1] - 1 for i in range(1, n) if p[i - 1]]
    rq = [q[i] / q[i - 1] - 1 for i in range(1, n) if q[i - 1]]
    m = min(len(rp), len(rq))
    rp, rq = rp[-m:], rq[-m:]
    if m < 20:
        return out
    mp, mq = sum(rp) / m, sum(rq) / m
    cov = sum((rp[i] - mp) * (rq[i] - mq) for i in range(m)) / (m - 1)
    varq = sum((x - mq) ** 2 for x in rq) / (m - 1)
    vp = math.sqrt(sum((x - mp) ** 2 for x in rp) / (m - 1))
    beta = cov / varq if varq > 0 else 0.0
    alpha_ann = (mp - beta * mq) * 252
    corr = cov / (vp * math.sqrt(varq)) if vp > 0 and varq > 0 else 0.0
    return {"available": True, "alpha_annual": round(alpha_ann, 4), "beta_qqq": round(beta, 3),
            "corr_qqq": round(corr, 3), "r2": round(corr * corr, 3),
            "preset_total": round(p[-1] / p[0] - 1, 4), "qqq_total": round(q[-1] / q[0] - 1, 4),
            "n_days": m}


# ─────────────────────────── Détection d'incidents (pur) ───────────────────────────
# Concentrations INTENTIONNELLES du cœur indiciel (50 % QQQ + ETF) → NE sont PAS des incidents.
_EXPECTED_BREACH_LABELS = {"QQQ", "ETF"}


def _current_drawdown(snapshot: dict) -> float | None:
    """Drawdown COURANT (dernier point vs plus-haut) de la courbe preset — pas le max historique."""
    curve = (snapshot.get("index_core_curves", {}) or {}).get("preset") or []
    v = [float(x) for x in curve if x is not None]
    if len(v) < 2:
        return None
    peak = max(v)
    return (v[-1] / peak - 1.0) if peak > 0 else None


def detect_incidents(snapshot: dict, kill_dd: float = _KILL_DD) -> list[dict]:
    """Renvoie les incidents à archiver : franchissement de limite VaR/risque (hors cœur indiciel
    intentionnel), kill-switch sur drawdown COURANT, échec du backtest de VaR (Kupiec). [] = RAS."""
    out: list[dict] = []
    p = snapshot.get("portfolio", {}) or {}
    an = p.get("analysis", {}) or {}
    limits = an.get("limits", {}) or {}
    risk = an.get("risk", {}) or {}
    breaches = [b for b in (limits.get("breaches") or [])
                if str(b.get("label", "")).upper() not in _EXPECTED_BREACH_LABELS]
    if breaches:
        out.append({"type": "limite_risque", "detail":
                    "; ".join(f"{b.get('type')}={b.get('label')} {b.get('weight')}>{b.get('limit')}" for b in breaches)})
    dd_now = _current_drawdown(snapshot)
    if dd_now is not None and dd_now <= -abs(kill_dd):
        out.append({"type": "kill_switch_drawdown", "detail": f"drawdown COURANT {dd_now*100:.1f}% ≤ −{kill_dd*100:.0f}%"})
    vb = risk.get("var_backtest") or {}
    if isinstance(vb, dict) and (vb.get("reject") is True or vb.get("kupiec_reject") is True):
        out.append({"type": "var_backtest_kupiec", "detail": "modèle de VaR rejeté (Kupiec) — recalibrer"})
    return out


# ─────────────────────────── Construction Markdown (pur) ───────────────────────────
def _meta_common(snapshot: dict, attr: dict) -> dict[str, Any]:
    d = snapshot.get("dashboard", {}) or {}
    metrics = d.get("metrics", {}) or {}
    reg = d.get("regime", {}) or {}
    risk = ((snapshot.get("portfolio", {}) or {}).get("analysis", {}) or {}).get("risk", {}) or {}
    limits = ((snapshot.get("portfolio", {}) or {}).get("analysis", {}) or {}).get("limits", {}) or {}
    garch = risk.get("garch") if isinstance(risk.get("garch"), dict) else {}
    dd_now = _current_drawdown(snapshot)
    return {
        "regime_cycle": reg.get("cycle"), "regime_risk": reg.get("risk_mode"),
        "vix": round(float(d.get("vix", 0) or 0), 1),
        "sharpe": metrics.get("sharpe"), "sortino": metrics.get("sortino"),
        "max_drawdown": metrics.get("max_drawdown"), "drawdown_now": None if dd_now is None else round(dd_now, 4),
        "var_95": risk.get("var_95"), "cvar_95": risk.get("cvar_95"),
        "garch_vol": (garch or {}).get("vol_forecast") or (garch or {}).get("sigma"),
        "alpha_annual": attr.get("alpha_annual"), "beta_qqq": attr.get("beta_qqq"),
        "kill_switch": bool(dd_now is not None and dd_now <= -_KILL_DD),
        "risk_limits_ok": bool(limits.get("ok", True)), "n_breaches": len(limits.get("breaches") or []),
    }


def _verdict(kill: bool, limits_ok: bool) -> tuple[str, str]:
    """(libellé, type de callout Obsidian) selon l'état de risque."""
    if kill:
        return "🔴 Incident", "danger"
    if not limits_ok:
        return "🟠 Vigilance", "warning"
    return "🟢 Nominal", "success"


def _ret_window(curve: list, lookback: int) -> float | None:
    v = [float(x) for x in (curve or []) if x is not None]
    if len(v) < 2:
        return None
    base = v[-min(lookback + 1, len(v))]
    return (v[-1] / base - 1.0) if base else None


def _week_perf(snapshot: dict, days: int = 5) -> dict:
    """Perf glissante (≈1 semaine) du preset vs QQQ, à partir des courbes réelles."""
    cur = snapshot.get("index_core_curves", {}) or {}
    rp, rq = _ret_window(cur.get("preset"), days), _ret_window(cur.get("qqq"), days)
    out = {"preset": rp, "qqq": rq, "excess": None, "days": days}
    if rp is not None and rq is not None:
        out["excess"] = round(rp - rq, 4)
    return out


def _contributors(snapshot: dict, days: int = 5, n: int = 5) -> tuple[list[dict], list[dict]]:
    """(top contributeurs, top détracteurs) = poids × rendement sur `days`, depuis l'alloc preset
    et les séries OHLC. Renvoie ([], []) si la donnée manque."""
    d = snapshot.get("dashboard", {}) or {}
    alloc = d.get("preset_allocation") or d.get("positions") or []
    series = d.get("chart_series", {}) or {}
    rows: list[dict] = []
    for a in alloc:
        sym = a.get("symbol")
        w = a.get("weight") or a.get("weight_pct")
        bars = series.get(sym)
        if not sym or w is None or not bars:
            continue
        ret = _ret_window([b.get("c") for b in bars], days)
        if ret is None:
            continue
        rows.append({"symbol": sym, "sector": a.get("sector", ""), "weight": float(w),
                     "ret": ret, "contrib": float(w) * ret})
    rows.sort(key=lambda r: r["contrib"], reverse=True)
    top = rows[:n]
    bottom = [r for r in rows[::-1] if r["contrib"] < 0][:n]
    return top, bottom


def daily_note(snapshot: dict, attr: dict, incidents: list[dict], date: str | None = None,
               svg_asset: str | None = None) -> tuple[str, str]:
    """Note journalière — design épuré (TL;DR + tables groupées). PUR."""
    dt = date or datetime.now(timezone.utc).date().isoformat()
    d = snapshot.get("dashboard", {}) or {}
    metrics = d.get("metrics", {}) or {}
    risk = ((snapshot.get("portfolio", {}) or {}).get("analysis", {}) or {}).get("risk", {}) or {}
    limits = ((snapshot.get("portfolio", {}) or {}).get("analysis", {}) or {}).get("limits", {}) or {}
    led = (snapshot.get("preset_ledger", {}) or {}).get("summary", {}) or {}
    reg = d.get("regime", {}) or {}
    meta = {"type": "daily_journal", "date": dt, "tags": ["quant", "journal"], **_meta_common(snapshot, attr)}
    regime_link = f"[[Régime_{reg.get('risk_mode', 'neutral')}]]"
    kill, ok = meta["kill_switch"], limits.get("ok", True)
    verdict, ctype = _verdict(kill, ok)

    P: list[str] = [_yaml_front_matter(meta), "", f"# 📓 {dt} · Journal quant", "",
                    f"> [!{ctype}] {verdict} — {regime_link} ({reg.get('cycle','?')}) · VIX **{_f(d.get('vix'),1)}** · "
                    f"Sharpe **{_f(metrics.get('sharpe'))}** · MaxDD **{_pct(metrics.get('max_drawdown'))}** · "
                    f"Alpha **{_pct(attr.get('alpha_annual'))}**",
                    f"> Stratégie {d.get('strategy_label','—')} · [[Preset_Performance]] · [[07_RISK_POLICY]]", ""]
    if kill:
        P += [f"> [!danger] KILL-SWITCH ACTIF — drawdown courant {_pct(meta.get('drawdown_now'))} ≤ −{int(_KILL_DD*100)} %. "
              "Exposition coupée jusqu'à revue.", ""]
    elif not ok:
        P += ["> [!warning] Budget de risque dépassé — "
              + " · ".join(f"{b.get('label')} {_pct(b.get('weight'))} > {_pct(b.get('limit'))}"
                           for b in (limits.get("breaches") or [])), ""]
    # métriques groupées (perf | risque) — compact, aligné
    P += ["## Métriques clés", "",
          "| Performance |  | Risque |  |", "|---|--:|---|--:|",
          f"| Rendement | {_pct(metrics.get('total_return'))} | VaR 95 % | {_pct(risk.get('var_95'))} |",
          f"| Sharpe | {_f(metrics.get('sharpe'))} | CVaR 95 % | {_pct(risk.get('cvar_95'))} |",
          f"| Sortino | {_f(metrics.get('sortino'))} | Vol GARCH | {_pct(meta.get('garch_vol'))} |",
          f"| Calmar | {_f(metrics.get('calmar'))} | DD courant | {_pct(meta.get('drawdown_now'))} |",
          f"| Max DD | {_pct(metrics.get('max_drawdown'))} | Frais nets | {_pct(led.get('fees_pct'),2)} |", ""]
    if attr.get("available"):
        P += [f"> [!note] **Attribution nette de frais** — Alpha annualisé **{_pct(attr.get('alpha_annual'))}**, "
              f"Beta QQQ **{_f(attr.get('beta_qqq'))}**, R² **{_f(attr.get('r2'))}** · "
              f"Preset {_pct(attr.get('preset_total'))} vs QQQ {_pct(attr.get('qqq_total'))}.", ""]
    if svg_asset:
        P += [f"![[{svg_asset}]]", ""]
    # statut de risque en une ligne (plus dense qu'un flowchart décoratif)
    P += [f"> [!{'danger' if kill else 'warning' if not ok else 'note'}] **Risque** — "
          f"régime {reg.get('risk_mode','?')} · limites {'OK' if ok else 'FRANCHIES'} · "
          f"kill-switch {'ACTIF' if kill else 'armé'}.", ""]
    if incidents:
        P += ["## ⚠️ Incidents", "",
              *[f"- [[{_POSTMORTEM_DIR}/incident_{dt}|{i['type']}]] — {i['detail']}" for i in incidents], ""]
    P += ["---", "<small>Point-in-time · n'interrompt jamais le trading.</small>"]
    return f"{_JOURNAL_DIR}/{dt}.md", "\n".join(P)


def weekly_note(snapshot: dict, attr: dict, date: str | None = None) -> tuple[str, str]:
    """Synthèse hebdomadaire — perf 7 j, top contributeurs/détracteurs, dérive de l'alpha. PUR."""
    dt_obj = datetime.fromisoformat(date) if date else datetime.now(timezone.utc)
    iso = dt_obj.isocalendar()
    wk = f"{iso[0]}-W{iso[1]:02d}"
    perf = _week_perf(snapshot)
    top, bottom = _contributors(snapshot)
    meta = {"type": "weekly_review", "date": dt_obj.date().isoformat(), "week": wk,
            "tags": ["quant", "weekly"], **_meta_common(snapshot, attr)}
    P = [_yaml_front_matter(meta), "", f"# 🗓️ {wk} · Synthèse hebdomadaire", "",
         f"> [!info] Preset **{_pct(perf['preset'])}** vs QQQ **{_pct(perf['qqq'])}** → excès **{_pct(perf['excess'])}** "
         f"(≈{perf['days']} j) · Alpha annualisé **{_pct(attr.get('alpha_annual'))}** · Beta **{_f(attr.get('beta_qqq'))}**",
         f"> [[Preset_Performance]] · [[10_BACKTEST_RESULTS]]", ""]
    if top:
        P += ["## 🏆 Top contributeurs", "", "| Actif | Secteur | Poids | Perf | Contrib |", "|---|---|--:|--:|--:|",
              *[f"| [[{r['symbol']}]] | {r['sector']} | {_pct(r['weight'])} | {_pct(r['ret'])} | {_pct(r['contrib'],2)} |"
                for r in top], ""]
    if bottom:
        P += ["## 🧊 Détracteurs", "", "| Actif | Secteur | Poids | Perf | Contrib |", "|---|---|--:|--:|--:|",
              *[f"| [[{r['symbol']}]] | {r['sector']} | {_pct(r['weight'])} | {_pct(r['ret'])} | {_pct(r['contrib'],2)} |"
                for r in bottom], ""]
    if not top and not bottom:
        P += ["> [!note] Contributions par actif indisponibles (séries OHLC absentes de ce build).", ""]
    P += ["---", f"<small>Synthèse {wk} · générée {dt_obj.date().isoformat()}.</small>"]
    return f"06_Weekly/{wk}.md", "\n".join(P)


def incident_note(snapshot: dict, incident: dict, date: str | None = None) -> tuple[str, str]:
    """Post-mortem isolé — snapshot exact de la rupture, design audit. PUR."""
    dt = date or datetime.now(timezone.utc).date().isoformat()
    d = snapshot.get("dashboard", {}) or {}
    metrics = d.get("metrics", {}) or {}
    risk = ((snapshot.get("portfolio", {}) or {}).get("analysis", {}) or {}).get("risk", {}) or {}
    limits = ((snapshot.get("portfolio", {}) or {}).get("analysis", {}) or {}).get("limits", {}) or {}
    positions = (d.get("preset_allocation") or d.get("positions") or [])
    meta = {"type": "incident", "date": dt, "incident_type": incident.get("type"),
            "tags": ["quant", "incident", "post_mortem"], **_meta_common(snapshot, {})}
    top = sorted(positions, key=lambda r: -(r.get("weight") or r.get("weight_pct") or 0))[:10]
    P = [_yaml_front_matter(meta), "", f"# 🚨 {dt} · Post-mortem — {incident.get('type')}", "",
         f"> [!danger] {incident.get('detail','')}", "",
         "## Snapshot de la rupture", "", "| Indicateur | Valeur |", "|---|--:|",
         f"| VIX | {_f(d.get('vix'),1)} |",
         f"| Régime | {d.get('regime',{}).get('risk_mode','?')} / {d.get('regime',{}).get('cycle','?')} |",
         f"| Drawdown courant | {_pct(meta.get('drawdown_now'))} |",
         f"| VaR 95 % / CVaR 95 % | {_pct(risk.get('var_95'))} / {_pct(risk.get('cvar_95'))} |",
         f"| Concentration top | {limits.get('top_name','—')} {_pct(limits.get('top_name_weight'))} |", "",
         "## Carnet — top 10 expositions", "", "| Actif | Secteur | Poids |", "|---|---|--:|",
         *[f"| [[{r.get('symbol','?')}]] | {r.get('sector','')} | {_pct(r.get('weight') or r.get('weight_pct'))} |" for r in top],
         "", "## Actions correctives", "",
         "- [ ] Cause racine identifiée", "- [ ] Réduction d'exposition décidée",
         "- [ ] Mise à jour [[07_RISK_POLICY]]", "",
         f"<small>Lié : [[{_JOURNAL_DIR}/{dt}]] · [[Preset_Performance]]</small>"]
    return f"{_POSTMORTEM_DIR}/incident_{dt}.md", "\n".join(P)


def preset_performance_hub(snapshot: dict, attr: dict, date: str | None = None) -> tuple[str, str]:
    """Hub [[Preset_Performance]] — résumé + index Dataview. PUR."""
    dt = date or datetime.now(timezone.utc).date().isoformat()
    meta = {"type": "attribution_hub", "date": dt, "tags": ["quant", "hub"], **_meta_common(snapshot, attr)}
    P = [_yaml_front_matter(meta), "", "# 📈 Preset_Performance", "",
         f"> [!abstract] Alpha net annualisé **{_pct(attr.get('alpha_annual'))}** · Beta QQQ "
         f"**{_f(attr.get('beta_qqq'))}** · R² **{_f(attr.get('r2'))}** — maj {dt}", "",
         "## Journaux récents", "", "```dataview",
         "table sharpe as Sharpe, max_drawdown as MaxDD, var_95 as VaR, alpha_annual as Alpha, kill_switch as Kill",
         "from #journal sort date desc limit 30", "```", "",
         "## Synthèses hebdomadaires", "", "```dataview",
         "table alpha_annual as Alpha, beta_qqq as Beta from #weekly sort date desc", "```", "",
         "## Incidents", "", "```dataview",
         "table incident_type as Type, drawdown_now as DD, vix as VIX from #incident sort date desc", "```", "",
         "## Notes par société", "", "```dataview",
         "table score as Score, recommendation as Reco, roce as ROCE, margin_of_safety as Sécurité",
         "from #company sort score desc", "```", "",
         "Réf. : [[07_RISK_POLICY]] · [[10_BACKTEST_RESULTS]] · [[06_STRATEGIES]]"]
    return _HUB_NOTE, "\n".join(P)



# ─────────────────────────── Orchestration (robuste) ───────────────────────────
class ObsidianVault:
    """Accès disque au coffre (écritures atomiques, jamais bloquantes)."""

    def __init__(self, root: str | os.PathLike | None = None) -> None:
        self.root = Path(root) if root else _VAULT

    def write(self, relpath: str, content: str) -> bool:
        return _atomic_write(self.root / relpath, content)


def sync_obsidian_vault(snapshot: dict | None = None, root: str | os.PathLike | None = None) -> dict:
    """Génère/rafraîchit le coffre (journal du jour, hub d'attribution, post-mortems).

    ROBUSTE : ne LÈVE JAMAIS — toute erreur est journalisée et renvoyée dans le résumé, afin de ne
    pas bloquer la clôture/le trading. Construit le snapshot si non fourni (import paresseux du cœur).
    """
    res: dict[str, Any] = {"ok": False, "written": [], "incidents": 0, "errors": []}
    try:
        if snapshot is None:
            try:
                from apps.api.snapshot import build_snapshot
                snapshot = build_snapshot()
            except Exception as e:  # noqa: BLE001
                res["errors"].append(f"snapshot: {e}")
                return res
        vault = ObsidianVault(root)
        dt = datetime.now(timezone.utc).date().isoformat()
        attr = compute_attribution(snapshot)
        incidents = detect_incidents(snapshot)
        # sparkline SVG de la courbe preset (net)
        svg_asset = None
        try:
            curve = (snapshot.get("index_core_curves", {}) or {}).get("preset") or []
            svg = _svg_sparkline(curve)
            if svg and vault.write(f"{_ASSETS_DIR}/equity_{dt}.svg", svg):
                svg_asset = f"{_ASSETS_DIR}/equity_{dt}.svg"
        except Exception as e:  # noqa: BLE001
            res["errors"].append(f"svg: {e}")
        # notes
        for builder in (lambda: daily_note(snapshot, attr, incidents, dt, svg_asset),
                        lambda: weekly_note(snapshot, attr, dt),
                        lambda: preset_performance_hub(snapshot, attr, dt)):
            try:
                rel, content = builder()
                if vault.write(rel, content):
                    res["written"].append(rel)
            except Exception as e:  # noqa: BLE001
                res["errors"].append(str(e))
        for inc in incidents:
            try:
                rel, content = incident_note(snapshot, inc, dt)
                if vault.write(rel, content):
                    res["written"].append(rel)
            except Exception as e:  # noqa: BLE001
                res["errors"].append(str(e))
        # stub de régime (pour que le lien [[Régime_...]] résolve)
        reg = (snapshot.get("dashboard", {}) or {}).get("regime", {}) or {}
        rk = reg.get("risk_mode", "neutral")
        vault.write(f"{_REGIMES_DIR}/Régime_{rk}.md",
                    f"---\ntype: regime\nrisk_mode: {rk}\n---\n\n# Régime {rk}\n\n"
                    f"Notes liées : `#journal` en régime **{rk}**.\n")
        res["incidents"] = len(incidents)
        res["ok"] = True
    except Exception as e:  # noqa: BLE001 — ULTIME garde-fou : jamais d'exception remontée
        res["errors"].append(f"fatal: {e}")
        log.warning("sync_obsidian_vault: %s", e)
    return res


def main() -> None:
    import json
    print(json.dumps(sync_obsidian_vault(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
