"""Cadre d'audit continu des données (standards type ISAE 3402 / PwC) — stdlib pur, testable.

Trois piliers : COMPLÉTUDE (trous, bougies manquantes), EXACTITUDE (prix aberrants, OHLC
incohérent, splits non ajustés, volumes nuls), TRAÇABILITÉ POINT-IN-TIME (aucune date future,
biais du survivant via data/delisted.csv). Sépare les anomalies par sévérité ; `assert_integrity`
lève une exception CRITIQUE pour bloquer un build qui corromprait l'intégrité.

Aucune dépendance lourde : fonctionne sur les `Bar` (objets .ts/.open/.high/.low/.close/.volume)
ou des dicts {ts/o/h/l/c/v}. JAMAIS bloquant hors `assert_integrity` (qui est explicite)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SEVERITIES = ("critical", "major", "warning")


class DataIntegrityError(RuntimeError):
    """Levée par assert_integrity() si ≥1 anomalie CRITIQUE (build/ingest doit échouer)."""


@dataclass(frozen=True, slots=True)
class Anomaly:
    symbol: str
    kind: str
    severity: str           # critical | major | warning
    detail: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AuditReport:
    anomalies: list[Anomaly] = field(default_factory=list)
    n_symbols: int = 0
    n_bars: int = 0

    @property
    def critical(self) -> list[Anomaly]:
        return [a for a in self.anomalies if a.severity == "critical"]

    @property
    def ok(self) -> bool:
        return len(self.critical) == 0

    def counts(self) -> dict[str, int]:
        return {s: sum(1 for a in self.anomalies if a.severity == s) for s in SEVERITIES}

    def to_dict(self) -> dict:
        return {"ok": self.ok, "n_symbols": self.n_symbols, "n_bars": self.n_bars,
                "counts": self.counts(), "anomalies": [a.to_dict() for a in self.anomalies[:500]]}


# ─────────────────────────── helpers ───────────────────────────
def _get(bar: Any, *names: str) -> float | None:
    for n in names:
        if isinstance(bar, dict):
            if n in bar and bar[n] is not None:
                try:
                    return float(bar[n])
                except (TypeError, ValueError):
                    return None
        else:
            v = getattr(bar, n, None)
            if v is not None:
                try:
                    return float(v)
                except (TypeError, ValueError):
                    return None
    return None


def _ts(bar: Any) -> date | None:
    v = bar.get("ts") or bar.get("t") if isinstance(bar, dict) else getattr(bar, "ts", None)
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return datetime.fromisoformat(str(v)[:10]).date()
    except ValueError:
        return None


def _business_days(d0: date, d1: date) -> int:
    """Nombre de jours ouvrés (lun-ven) entre d0 et d1 inclus — proxy de calendrier de cotation."""
    if d1 < d0:
        return 0
    days = (d1 - d0).days + 1
    full, rem = divmod(days, 7)
    n = full * 5
    start = d0.weekday()
    for i in range(rem):
        if (start + i) % 7 < 5:
            n += 1
    return n


def _calendar_days(d0: date, d1: date) -> int:
    """Jours calendaires (365/an) entre d0 et d1 inclus — marchés 24/7 (crypto)."""
    return (d1 - d0).days + 1 if d1 >= d0 else 0


def _is_crypto(symbol: str) -> bool:
    """Heuristique crypto (marché 24/7) : paires /USDC,/USDT ou suffixe -USD/-USDT."""
    s = symbol.upper()
    return "/USDC" in s or "/USDT" in s or s.endswith(("-USD", "-USDT"))


# ─────────────────────────── audit par série ───────────────────────────
def audit_series(symbol: str, bars: Iterable[Any], *, now: date | None = None,
                 max_gap_ratio: float = 0.10, split_jump: float = 0.50,
                 stale_run: int = 10, min_bars: int = 60) -> list[Anomaly]:
    """Audite UNE série OHLCV. Renvoie la liste d'anomalies (vide = conforme)."""
    bars = list(bars)
    out: list[Anomaly] = []
    today = now or datetime.now(timezone.utc).date()
    if len(bars) < min_bars:
        out.append(Anomaly(symbol, "completeness", "warning", f"série courte : {len(bars)} barres (<{min_bars})"))
    prev_c: float | None = None
    stale = 0
    dates: list[date] = []
    for b in bars:
        o, h, l, c = _get(b, "open", "o"), _get(b, "high", "h"), _get(b, "low", "l"), _get(b, "close", "c")
        v = _get(b, "volume", "v")
        d = _ts(b)
        if d:
            dates.append(d)
            if d > today:                                  # FUITE POINT-IN-TIME : date future
                out.append(Anomaly(symbol, "point_in_time", "critical", f"barre future {d} > {today}"))
        for name, val in (("open", o), ("high", h), ("low", l), ("close", c)):
            if val is not None and val <= 0:
                out.append(Anomaly(symbol, "accuracy", "critical", f"{name} ≤ 0 ({val}) le {d}"))
        if h is not None and l is not None and h < l:
            out.append(Anomaly(symbol, "accuracy", "critical", f"high<low ({h}<{l}) le {d}"))
        if c is not None and h is not None and l is not None and not (l - 1e-9 <= c <= h + 1e-9):
            out.append(Anomaly(symbol, "accuracy", "major", f"close hors [low,high] le {d}"))
        if v is not None and v < 0:
            out.append(Anomaly(symbol, "accuracy", "major", f"volume négatif ({v}) le {d}"))
        if prev_c and c:
            r = c / prev_c - 1.0
            if abs(r) >= split_jump:                       # saut brutal = split non ajusté probable
                out.append(Anomaly(symbol, "accuracy", "warning", f"saut {r*100:.0f}% le {d} (split non ajusté ?)"))
            stale = stale + 1 if abs(r) < 1e-9 else 0
            if stale == stale_run:
                out.append(Anomaly(symbol, "accuracy", "warning", f"prix figé {stale_run} j consécutifs (≈{d})"))
        prev_c = c if c else prev_c
    # complétude : trous vs calendrier (crypto = 365 j/an ; sinon jours ouvrés)
    if len(dates) >= 2:
        if _is_crypto(symbol):
            expected = _calendar_days(min(dates), max(dates))
            cal = "j calendaires"
        else:
            expected = _business_days(min(dates), max(dates))
            cal = "j ouvrés"
        ratio = 1.0 - (len(dates) / expected) if expected else 0.0
        if ratio > max_gap_ratio:
            msg = f"{ratio*100:.0f}% manquantes ({len(dates)}/{expected} {cal})"
            out.append(Anomaly(symbol, "completeness", "major", msg))
    return out


def audit_dataset(data: dict[str, Iterable[Any]], *, now: date | None = None, **kw: Any) -> AuditReport:
    """Audite TOUT le jeu de données (par symbole). Renvoie un rapport agrégé."""
    rep = AuditReport(n_symbols=len(data))
    for sym, bars in data.items():
        blist = list(bars)
        rep.n_bars += len(blist)
        rep.anomalies.extend(audit_series(sym, blist, now=now, **kw))
    return rep


def survivorship_check(universe_symbols: Iterable[str], delisted_path: str | Path | None = None) -> Anomaly | None:
    """Biais du survivant : signale l'absence de data/delisted.csv (backtests longs optimistes)."""
    p = Path(delisted_path) if delisted_path else (Path(__file__).resolve().parents[2] / "data" / "delisted.csv")
    if not p.exists():
        return Anomaly("*", "survivorship", "warning",
                       "data/delisted.csv absent → univers survivant uniquement (backtests longs optimistes)")
    return None


def assert_integrity(report: AuditReport) -> None:
    """Bloque le pipeline si anomalies CRITIQUES (contrat de régression CI/CD)."""
    crit = report.critical
    if crit:
        sample = "; ".join(f"{a.symbol}:{a.kind}:{a.detail}" for a in crit[:5])
        raise DataIntegrityError(f"{len(crit)} anomalie(s) CRITIQUE(s) : {sample}")


def audit_and_report(data: dict, *, universe: Iterable[str] | None = None,
                     now: date | None = None) -> AuditReport:
    """Point d'entrée pipeline : audite données + biais du survivant. Best-effort (ne lève pas)."""
    rep = audit_dataset(data, now=now)
    surv = survivorship_check(universe or list(data))
    if surv:
        rep.anomalies.append(surv)
    return rep
