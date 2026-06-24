"""Event-store point-in-time — fondation alt-data → alpha (0 dépendance).

Clé d'or (Gardien) : `ts_public` = instant où l'info devient PUBLIQUE → anti look-ahead.
Ontologie légère (Karp) : un Event porte ses entités (tickers) + sa provenance.
JSONL append-only (souverain). DuckDB/Parquet = voie d'échelle (ASOF JOIN, Ghodsi).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

DEFAULT_PATH = Path("research/events.jsonl")


@dataclass(frozen=True)
class Event:
    ts_public: str                      # ISO 8601 — instant PUBLIC (clé anti-lookahead)
    type: str                           # ex. insider_buy, earnings, 8k
    tickers: tuple[str, ...]            # entités liées (résolues point-in-time)
    source: str                         # provenance (ex. "sec_edgar")
    ts_event: str | None = None         # survenance (≤ ts_public) — info seulement
    meta: dict = field(default_factory=dict)

    @property
    def hash(self) -> str:
        key = (f"{self.ts_public}|{self.type}|"
               f"{','.join(sorted(self.tickers))}|{self.source}")
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["tickers"] = list(self.tickers)
        d["hash"] = self.hash
        return d


def load_events(path: str | Path = DEFAULT_PATH) -> list[dict]:
    """Lit tous les events (ignore lignes vides/corrompues, jamais bloquant)."""
    p = Path(path)
    if not p.exists():
        return []
    out: list[dict] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def append_events(events, path: str | Path = DEFAULT_PATH) -> int:
    """Ajoute des events (dédup par hash). Retourne le nombre RÉELLEMENT ajouté."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    seen = {e.get("hash") for e in load_events(path)}
    added = 0
    with p.open("a", encoding="utf-8") as fh:
        for ev in events:
            d = ev.to_dict() if isinstance(ev, Event) else dict(ev)
            if "hash" not in d:                     # event brut sans hash calculé
                d["hash"] = Event(d["ts_public"], d["type"],
                                  tuple(d.get("tickers", [])), d.get("source", "")).hash
            if d["hash"] in seen:
                continue
            fh.write(json.dumps(d, ensure_ascii=False, sort_keys=True) + "\n")
            seen.add(d["hash"])
            added += 1
    return added
