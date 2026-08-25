"""Alertes techniques TradingView → **veto / kill-switch** du Risk Engine.

Flux : TradingView (alerte Pine/indicateur) → webhook HTTP `POST /api/tv/webhook` → fichier
`.cache/tv_alerts.json` (drop). Ici on LIT ce drop (polling) et on le mappe en signal de veto.

⚠️ LIVE-ONLY : ces alertes n'alimentent QUE la décision en temps réel (réduire/bloquer l'expo).
Elles ne sont JAMAIS injectées dans le backtest ni l'entraînement ML (aucune fuite point-in-time).
Robuste : fichier absent/corrompu → liste vide (le risk-engine continue sans veto, jamais de crash).

DEUX DÉFAUTS CORRIGÉS LE 25/08, tous deux sur le chemin du kill-switch.

1. `max_age_s` ÉTAIT DÉCLARÉ, DOCUMENTÉ, ET JAMAIS APPLIQUÉ. Le corps de la fonction ignorait
   le paramètre. Conséquence mesurée : une alerte `critical` reçue le 1er juillet vetoait encore
   tout le trading des semaines plus tard, et `run_live.py` appelait la fonction SANS argument —
   donc une seule alerte critique bloquait le portefeuille jusqu'à effacement manuel du drop.
   Le défaut par défaut est désormais un filtre ACTIF (`AGE_MAX_DEFAUT`) : `None` reste possible
   mais doit être demandé explicitement, parce que « aucun filtre » est le réglage dangereux.

2. UNE SÉVÉRITÉ INCONNUE ÉTAIT DÉGRADÉE EN `info`. Une alerte Pine étiquetée « urgent » ou
   « CRITIQUE » (le mot français, plausible pour un utilisateur francophone) devenait `info` et
   ne déclenchait rien. Un kill-switch qui ignore silencieusement une alerte nommée CRITIQUE est
   pire que pas de kill-switch : on le croit armé. Une sévérité non reconnue vaut désormais
   `warning` — on ne descend jamais vers « rien ne se passe » sur une entrée qu'on n'a pas
   comprise — et elle est SIGNALÉE pour qu'une faute de frappe devienne visible.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_PATH = _ROOT / ".cache" / "tv_alerts.json"
_SEVERITIES = ("info", "warning", "critical")

# Âge maximal d'une alerte qui pèse encore sur la décision. Une alerte technique décrit un état
# de marché ; passé un jour, elle décrit le passé. Passer `None` désactive le filtre — ce qui
# doit rester un choix explicite, jamais un défaut.
AGE_MAX_DEFAUT = 24 * 3600.0

# Synonymes acceptés, français inclus : une alerte Pine est écrite à la main, souvent dans la
# langue de son auteur. Ce qui n'est pas dans cette table vaut `warning`, jamais `info`.
_SYNONYMES = {
    "crit": "critical", "high": "critical", "severe": "critical", "critique": "critical",
    "urgent": "critical", "grave": "critical", "danger": "critical", "error": "critical",
    "warn": "warning", "med": "warning", "medium": "warning", "attention": "warning",
    "avertissement": "warning", "alerte": "warning",
    "low": "info", "notice": "info", "debug": "info", "information": "info",
}


@dataclass(frozen=True, slots=True)
class TVAlert:
    """Alerte normalisée venue de TradingView."""

    time: str
    ticker: str
    kind: str                       # ex. "vix_spike", "trend_break", "circuit_breaker"
    severity: str = "info"          # info | warning | critical
    message: str = ""
    # Sévérité telle qu'ELLE A ÉTÉ REÇUE, si elle a dû être réinterprétée. Vide sinon. Sans ce
    # champ, une faute de frappe dans une alerte Pine reste invisible pour toujours.
    severite_brute: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def parse_alert(raw: dict) -> TVAlert | None:
    """Normalise un payload webhook TradingView (souple) en TVAlert, ou None si inexploitable."""
    if not isinstance(raw, dict):
        return None
    ticker = str(raw.get("ticker") or raw.get("symbol") or "").strip().upper()
    kind = str(raw.get("kind") or raw.get("type") or raw.get("alert") or "alert").strip()
    sev_brut = str(raw.get("severity") or raw.get("level") or "info").strip().lower()
    sev = sev_brut if sev_brut in _SEVERITIES else _SYNONYMES.get(sev_brut, "warning")
    if not ticker and not raw.get("message"):
        return None
    # Le drop est relu après écriture : la sévérité y est DÉJÀ normalisée, donc la comparaison
    # `sev_brut != sev` ne dirait plus rien. On conserve donc la trace déjà stockée si elle
    # existe — sinon l'information de réinterprétation ne survivrait pas à l'aller-retour fichier
    # et le diagnostic serait vide précisément quand on en a besoin.
    brute_stockee = str(raw.get("severite_brute") or "").strip().lower()
    return TVAlert(
        time=str(raw.get("time") or raw.get("timestamp") or time.strftime("%Y-%m-%dT%H:%M:%SZ")),
        ticker=ticker or "*", kind=kind, severity=sev,
        severite_brute=brute_stockee or (sev_brut if sev_brut != sev else ""),
        message=str(raw.get("message") or "")[:300],
    )


def append_alert(raw: dict, path: str | Path | None = None, keep: int = 200) -> TVAlert | None:
    """Ajoute une alerte au drop (appelé par le webhook de l'API). Borne l'historique à `keep`."""
    alert = parse_alert(raw)
    if alert is None:
        return None
    p = Path(path) if path else _DEFAULT_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        cur = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
        if not isinstance(cur, list):
            cur = []
    except (json.JSONDecodeError, OSError):
        cur = []
    cur.append(alert.to_dict())
    p.write_text(json.dumps(cur[-keep:], ensure_ascii=False), encoding="utf-8")
    return alert


def horodatage(alerte: TVAlert) -> "datetime | None":
    """Date de l'alerte, ou None si illisible. Tolérant : TradingView, un script Pine et un test
    n'écrivent pas le temps de la même façon, et un format inattendu ne doit pas faire échouer
    la lecture du drop entier."""
    brut = (alerte.time or "").strip()
    if not brut:
        return None
    txt = brut.replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(txt)
    except ValueError:
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M"):
            try:
                d = datetime.strptime(brut[:len(fmt) + 4], fmt)
                break
            except ValueError:
                continue
        else:
            return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def fetch_tv_technical_alerts(path: str | Path | None = None,
                              max_age_s: float | None = AGE_MAX_DEFAUT,
                              maintenant: "datetime | None" = None) -> list[TVAlert]:
    """Alertes TV encore PERTINENTES (polling du drop webhook).

    `max_age_s` était jusqu'au 25/08 déclaré et jamais appliqué : une alerte critique vieille de
    plusieurs semaines vetoait encore tout le portefeuille. Le filtre est maintenant ACTIF par
    défaut ; `max_age_s=None` désactive explicitement.

    Une alerte dont la date est ILLISIBLE est CONSERVÉE. Le choix est délibéré et va dans le sens
    prudent : entre « trader pendant un krach parce qu'on n'a pas su dater l'alerte » et « rester
    à l'écart le temps de comprendre », un kill-switch doit préférer le second. Elle est comptée
    dans `to_risk_veto` (`n_sans_date`) pour que la situation reste visible plutôt que subie.
    """
    p = Path(path) if path else _DEFAULT_PATH
    try:
        rows = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
    except (json.JSONDecodeError, OSError):
        return []
    out = [a for a in (parse_alert(r) for r in rows) if a is not None]
    if max_age_s is None:
        return out
    ref = maintenant or datetime.now(timezone.utc)
    limite = float(max_age_s)
    retenues = []
    for a in out:
        d = horodatage(a)
        if d is None or (ref - d).total_seconds() <= limite:
            retenues.append(a)
    return retenues


def to_risk_veto(alerts: list[TVAlert]) -> dict:
    """Mappe les alertes en décision risk-engine : veto si ≥1 alerte 'critical'.

    Returns: {"veto": bool, "reduce": float (0..1), "reasons": [...], "by_ticker": {...}}.
    'reduce' = facteur d'exposition conseillé (1=normal, 0.5 si warning, 0=veto total).
    """
    crit = [a for a in alerts if a.severity == "critical"]
    warn = [a for a in alerts if a.severity == "warning"]
    veto = len(crit) > 0
    reduce = 0.0 if veto else (0.5 if warn else 1.0)
    by_ticker: dict[str, str] = {}
    for a in alerts:
        if a.severity in ("critical", "warning"):
            by_ticker[a.ticker] = a.severity
    reasons = [f"{a.severity}:{a.kind} ({a.ticker})" for a in (crit + warn)][:10]
    # DIAGNOSTIC : sans ces deux compteurs, un veto permanent dû à une alerte non datable ou une
    # sévérité mal orthographiée reste invisible — on subit la décision sans pouvoir l'expliquer.
    sans_date = [a for a in alerts if horodatage(a) is None]
    reinterpretees = [f"« {a.severite_brute} » lu comme {a.severity} ({a.ticker})"
                      for a in alerts if a.severite_brute]
    return {"veto": veto, "reduce": reduce, "reasons": reasons, "by_ticker": by_ticker,
            "n_alerts": len(alerts), "n_sans_date": len(sans_date),
            "severites_reinterpretees": reinterpretees[:10]}
