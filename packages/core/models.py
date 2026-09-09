"""Domain models — pure, zero external dependency (stdlib only).

Ces modèles sont le langage commun de tout le système. Aucun module
(data, strategy, risk, UI...) ne définit ses propres types : tous parlent
ces objets-là. Volontairement en `dataclasses` + `Enum` stdlib pour garder
`core` sans aucune dépendance (cf. 01_ARCHITECTURE.md, règle « domaine pur »).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #
class AssetClass(str, Enum):
    EQUITY = "equity"
    ETF = "etf"
    INDEX = "index"
    FOREX = "forex"
    CRYPTO = "crypto"
    COMMODITY = "commodity"


class Side(str, Enum):
    LONG = "long"
    SHORT = "short"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderStatus(str, Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class SignalDirection(str, Enum):
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"  # close / no position


class CyclePhase(str, Enum):
    EXPANSION = "expansion"
    SLOWDOWN = "slowdown"
    RECESSION = "recession"
    RECOVERY = "recovery"


class RiskMode(str, Enum):
    RISK_ON = "risk_on"
    RISK_OFF = "risk_off"
    NEUTRAL = "neutral"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Instrument & market data
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Instrument:
    """Une ligne de la table maître de l'univers."""

    symbol: str
    asset_class: AssetClass
    venue: str
    currency: str = "USD"
    tz: str = "UTC"
    taker_fee_bps: float = 0.0  # frais en points de base
    maker_fee_bps: float = 0.0


@dataclass(frozen=True, slots=True)
class Bar:
    """Barre OHLCV normalisée — timestamp toujours UTC, close de la barre `t`."""

    instrument: str
    timeframe: str  # ex. "1m", "1h", "1d"
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


# --------------------------------------------------------------------------- #
# Signals, factors, regime
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class FactorScore:
    """Score d'un facteur pour un actif à une date (z-score cross-sectional)."""

    instrument: str
    factor: str  # "momentum_12_1", "value_ev_ebitda", "quality_roic"...
    value: float
    ts: datetime
    sector: str | None = None


@dataclass(frozen=True, slots=True)
class MacroObservation:
    """Observation macro VINTAGE (point-in-time).

    `obs_date` = période observée (ex. mois de la donnée).
    `realtime_start` = date à laquelle cette valeur a été PUBLIÉE/connue (vintage ALFRED).
    Une requête `as_of(t)` ne doit retourner que des observations avec realtime_start <= t.
    """

    series_id: str
    obs_date: datetime
    value: float
    realtime_start: datetime  # date de publication/connaissance (anti-fuite)


@dataclass(frozen=True, slots=True)
class EconomicRelease:
    """Publication d'un indicateur : réalisé vs consensus → surprise."""

    series_id: str
    release_date: datetime
    actual: float
    consensus: float
    std: float = 1.0  # écart-type historique des surprises (pour normaliser)

    @property
    def surprise_z(self) -> float:
        if self.std == 0:
            return 0.0
        return (self.actual - self.consensus) / self.std


@dataclass(frozen=True, slots=True)
class RegimeState:
    """État macro/régime quotidien, point-in-time, consommé par tous les modules."""

    ts: datetime
    cycle: CyclePhase
    risk_mode: RiskMode
    vix: float | None = None
    extras: dict[str, Any] = field(default_factory=dict)  # surprises éco, breadth...


@dataclass(frozen=True, slots=True)
class Signal:
    """Intention émise par une stratégie. N'exécute rien (cf. event bus)."""

    instrument: str
    direction: SignalDirection
    strategy: str
    ts: datetime
    strength: float = 1.0  # [0, 1]
    stop: float | None = None
    target: float | None = None
    reason: str = ""
    features: dict[str, float] = field(default_factory=dict)  # snapshot pour le ML

    @property
    def reward_risk(self) -> float | None:
        """R:R si stop et target fournis, sinon None."""
        if self.stop is None or self.target is None:
            return None
        risk = abs(self._entry_ref - self.stop)
        if risk == 0:
            return None
        return abs(self.target - self._entry_ref) / risk

    @property
    def _entry_ref(self) -> float:
        # Référence d'entrée = milieu stop/target par défaut ; surchargé par le sizer
        # avec le prix réel à l'exécution. Ici neutre pour le calcul de R:R relatif.
        if self.stop is not None and self.target is not None:
            return (self.stop + self.target) / 2
        return 0.0


# --------------------------------------------------------------------------- #
# Orders & positions
# --------------------------------------------------------------------------- #
@dataclass(slots=True)
class Order:
    instrument: str
    side: Side
    qty: float
    order_type: OrderType = OrderType.MARKET
    limit_price: float | None = None
    stop_price: float | None = None
    status: OrderStatus = OrderStatus.PENDING
    client_id: str | None = None  # pour l'idempotence (retries)
    filled_qty: float | None = None  # qté réellement remplie (None = inconnu, jamais supposer plein)
    ts: datetime = field(default_factory=utcnow)


@dataclass(slots=True)
class Position:
    instrument: str
    side: Side
    qty: float
    avg_price: float  # PRU / cost basis
    opened_at: datetime = field(default_factory=utcnow)

    def unrealized_pnl(self, mark: float) -> float:
        direction = 1 if self.side is Side.LONG else -1
        return direction * (mark - self.avg_price) * self.qty


# --------------------------------------------------------------------------- #
# Exécution : ce qui s'est RÉELLEMENT passé
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Fill:
    """Résultat ÉCONOMIQUE d'un ordre exécuté.

    `Order` est une intention, `Fill` est un fait.

    Ce maillon manquait : `SimBroker.submit` calculait le prix d'exécution et la
    commission, les appliquait au cash, puis les jetait — le coût réel n'avait nulle
    part où vivre, et le journal écrivait 0,0 par défaut.

    LA RÈGLE (anti double comptage). Le slippage est DÉJÀ dans `fill_price` : il a été
    payé à l'exécution et il est déjà dans tout P&L calculé sur des prix de fill.
    `shortfall_amount` est donc **descriptif** — il documente un coût subi, il ne se
    retranche pas une seconde fois :

        pnl_net = pnl_gross − commission − fees_other      ← jamais − shortfall_amount

    `source` n'a que deux valeurs et c'est ce qui empêche le mensonge : `observed` quand
    le courtier a donné le chiffre, `estimated` quand il vient d'un modèle de coûts.
    """

    instrument: str
    side: Side
    qty: float
    fill_price: float
    reference_price: float | None = None   # prix de décision — None si inconnu
    commission: float = 0.0
    fees_other: float = 0.0
    shortfall_bps: float | None = None     # None = non mesurable, ≠ 0.0 (parfait)
    currency: str = "USD"
    source: str = "estimated"              # "observed" | "estimated"
    ts: datetime = field(default_factory=utcnow)

    @property
    def notional(self) -> float:
        return self.fill_price * self.qty

    @property
    def charge(self) -> float:
        """Ce qui se RETRANCHE du P&L. Le shortfall n'y est pas : déjà dans le prix."""
        return self.commission + self.fees_other

    @property
    def shortfall_amount(self) -> float | None:
        """Coût de délai + exécution en devise. DESCRIPTIF — déjà payé dans le prix.

        Rapporté au notionnel de RÉFÉRENCE, pas à celui du fill : c'est la convention
        de l'implementation shortfall, et c'est la seule qui redonne exactement
        `(fill − référence) × qty`. Sur le notionnel du fill, un achat à +5 bps rendrait
        0,50025 $ au lieu de 0,50 $ — l'écart est petit, mais un coût qui ne se
        reconstitue pas à la main est un coût qu'on ne peut pas vérifier.
        """
        if self.shortfall_bps is None or self.reference_price is None:
            return None
        return self.shortfall_bps / 1e4 * self.reference_price * self.qty

    @property
    def cout_total_portefeuille(self) -> float:
        """Ce que l'ordre sort réellement du portefeuille : notionnel + charge."""
        return self.notional + self.charge


# --------------------------------------------------------------------------- #
# Trade journal (miroir de la table du Module 8)
# --------------------------------------------------------------------------- #
@dataclass(slots=True)
class TradeRecord:
    id: str
    instrument: str
    asset_class: AssetClass
    venue: str
    side: Side
    qty: float
    entry_ts: datetime
    entry_price: float
    avg_price: float  # PRU
    exit_ts: datetime | None = None
    exit_price: float | None = None
    # `None` = JAMAIS RENSEIGNÉ, ce qui n'est pas « nul ». Le défaut à 0.0 rendait les
    # deux indiscernables : `make turnover-audit` annonçait « 0,00 $ » de frais sur un
    # journal où l'exécution n'avait jamais alimenté la colonne (mesuré le 09/09).
    fees: float | None = None          # commission + frais divers, en devise
    slippage: float | None = None      # DESCRIPTIF : déjà contenu dans les prix de fill
    entry_reason: str = ""
    exit_reason: str = ""
    regime: str | None = None
    strategy: str | None = None
    features_snapshot: dict[str, float] = field(default_factory=dict)  # non négociable
    pnl_gross: float | None = None
    pnl_net: float | None = None
    pnl_pct: float | None = None
    r_multiple: float | None = None
    is_win: bool | None = None
    duration_s: float | None = None
    mfe: float | None = None  # max favorable excursion
    mae: float | None = None  # max adverse excursion
