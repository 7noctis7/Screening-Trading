"""Modèles typés des overlays graphiques (dataclasses strictes, sérialisables JSON).

Pas de dépendance externe (pydantic non requis) : validation explicite via `validate()` qui lève
`ValueError`. Dates au format ISO `YYYY-MM-DD` (cohérent avec lightweight-charts & le reste du repo).
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SIDES = ("buy", "sell")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _check_date(d: str, ctx: str) -> str:
    s = str(d)[:10]
    if not _DATE.match(s):
        raise ValueError(f"{ctx}: date invalide '{d}' (attendu YYYY-MM-DD)")
    return s


def _num(x: object, ctx: str) -> float:
    try:
        v = float(x)  # type: ignore[arg-type]
    except (TypeError, ValueError) as e:
        raise ValueError(f"{ctx}: nombre invalide '{x}'") from e
    if v != v:  # NaN
        raise ValueError(f"{ctx}: NaN interdit")
    return v


@dataclass(frozen=True, slots=True)
class ChartMarker:
    """Marqueur achat/vente ▲▼ (journal de trades RÉEL/paper, net de frais)."""

    time: str
    side: str
    price: float | None = None
    text: str = ""

    def validate(self) -> "ChartMarker":
        t = _check_date(self.time, "ChartMarker.time")
        if self.side not in _SIDES:
            raise ValueError(f"ChartMarker.side doit être 'buy' ou 'sell' (reçu '{self.side}')")
        p = None if self.price is None else _num(self.price, "ChartMarker.price")
        object.__setattr__(self, "time", t)
        object.__setattr__(self, "price", p)
        return self

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RiskBand:
    """Point d'un cône de risque (VaR/EVT dynamique, no-trade band, vol cone) : borne haute/basse."""

    time: str
    upper: float
    lower: float

    def validate(self) -> "RiskBand":
        t = _check_date(self.time, "RiskBand.time")
        up, lo = _num(self.upper, "RiskBand.upper"), _num(self.lower, "RiskBand.lower")
        if up < lo:
            raise ValueError(f"RiskBand: upper ({up}) < lower ({lo}) à {t}")
        object.__setattr__(self, "time", t)
        object.__setattr__(self, "upper", up)
        object.__setattr__(self, "lower", lo)
        return self

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class BlackoutZone:
    """Zone verticale de blackout (ex. fenêtre de résultats trimestriels SEC EDGAR / FMP)."""

    start: str
    end: str
    label: str = "blackout"

    def validate(self) -> "BlackoutZone":
        s, e = _check_date(self.start, "BlackoutZone.start"), _check_date(self.end, "BlackoutZone.end")
        if e < s:
            raise ValueError(f"BlackoutZone: end ({e}) avant start ({s})")
        object.__setattr__(self, "start", s)
        object.__setattr__(self, "end", e)
        return self

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Overlay:
    """Ensemble d'overlays pour UN ticker (marqueurs + bandes de risque + blackouts)."""

    ticker: str
    markers: list[ChartMarker] = field(default_factory=list)
    bands: list[RiskBand] = field(default_factory=list)
    blackouts: list[BlackoutZone] = field(default_factory=list)
    source: str = "mcp"
    as_of: str = field(default_factory=_utcnow)

    def validate(self) -> "Overlay":
        if not self.ticker or not str(self.ticker).strip():
            raise ValueError("Overlay.ticker requis")
        self.ticker = str(self.ticker).strip().upper()
        for m in self.markers:
            m.validate()
        for b in self.bands:
            b.validate()
        for z in self.blackouts:
            z.validate()
        # bandes triées par date (lightweight-charts exige des temps croissants)
        self.bands.sort(key=lambda b: b.time)
        return self

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker, "source": self.source, "as_of": self.as_of,
            "markers": [m.to_dict() for m in self.markers],
            "bands": [b.to_dict() for b in self.bands],
            "blackouts": [z.to_dict() for z in self.blackouts],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Overlay":
        return cls(
            ticker=d.get("ticker", ""),
            markers=[ChartMarker(**m) for m in d.get("markers", [])],
            bands=[RiskBand(**b) for b in d.get("bands", [])],
            blackouts=[BlackoutZone(**z) for z in d.get("blackouts", [])],
            source=d.get("source", "mcp"), as_of=d.get("as_of", _utcnow()),
        )
