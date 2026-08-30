"""Price-action causal : structure, zones FTB, SFP et profil de volume proxy.

OHLCV ne contient pas le carnet d'ordres. Ce plugin ne prétend donc pas détecter
des ordres institutionnels : il formalise des motifs de prix falsifiables,
à calibrer en walk-forward.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from statistics import median

from packages.core.models import Bar, Signal, SignalDirection
from packages.strategies.registry import strategies


@dataclass(frozen=True, slots=True)
class Zone:
    kind: str
    direction: int
    low: float
    high: float
    created: int

    @property
    def midpoint(self) -> float:
        return (self.low + self.high) / 2.0


def _true_ranges(bars: Sequence[Bar]) -> list[float]:
    out: list[float] = []
    for i, bar in enumerate(bars):
        prev = bars[i - 1].close if i else bar.open
        out.append(max(bar.high - bar.low, abs(bar.high - prev), abs(bar.low - prev)))
    return out


def confirmed_pivots(bars: Sequence[Bar], span: int) -> tuple[list[int], list[int]]:
    """Pivots connus seulement après `span` barres à droite (aucun back-painting)."""
    highs: list[int] = []
    lows: list[int] = []
    for i in range(span, len(bars) - span):
        window = bars[i - span : i + span + 1]
        if bars[i].high == max(bar.high for bar in window):
            highs.append(i)
        if bars[i].low == min(bar.low for bar in window):
            lows.append(i)
    return highs, lows


def _structure_events(bars: Sequence[Bar], span: int) -> list[tuple[int, int]]:
    highs, lows = confirmed_pivots(bars, span)
    events: list[tuple[int, int]] = []
    for pivot in highs:
        hit = next(
            (
                i
                for i in range(pivot + span + 1, len(bars))
                if bars[i].close > bars[pivot].high
            ),
            None,
        )
        if hit is not None:
            events.append((hit, 1))
    for pivot in lows:
        hit = next(
            (
                i
                for i in range(pivot + span + 1, len(bars))
                if bars[i].close < bars[pivot].low
            ),
            None,
        )
        if hit is not None:
            events.append((hit, -1))
    return sorted(events)


def structure_state(bars: Sequence[Bar], span: int) -> tuple[int, str]:
    """Biais et nature de la dernière cassure : BOS ou changement de caractère."""
    events = _structure_events(bars, span)
    if not events:
        return 0, "none"
    direction = events[-1][1]
    previous = events[-2][1] if len(events) > 1 else direction
    return direction, "choch" if previous != direction else "bos"


def structure_bias(bars: Sequence[Bar], span: int) -> int:
    return structure_state(bars, span)[0]


def _completed_htf(bars: Sequence[Bar], multiple: int) -> list[Bar]:
    completed = len(bars) // multiple
    out: list[Bar] = []
    for block in range(completed):
        chunk = bars[block * multiple : (block + 1) * multiple]
        out.append(
            Bar(
                chunk[0].instrument,
                f"{multiple}x{chunk[0].timeframe}",
                chunk[-1].ts,
                chunk[0].open,
                max(x.high for x in chunk),
                min(x.low for x in chunk),
                chunk[-1].close,
                sum(x.volume for x in chunk),
            )
        )
    return out


def _fvg_zones(bars: Sequence[Bar]) -> list[Zone]:
    zones: list[Zone] = []
    for i in range(2, len(bars)):
        if bars[i].low > bars[i - 2].high:
            zones.append(Zone("fvg", 1, bars[i - 2].high, bars[i].low, i))
        elif bars[i].high < bars[i - 2].low:
            zones.append(Zone("fvg", -1, bars[i].high, bars[i - 2].low, i))
    return zones


def _order_blocks(bars: Sequence[Bar], span: int, displacement: float) -> list[Zone]:
    trs = _true_ranges(bars)
    highs, lows = confirmed_pivots(bars, span)
    zones: list[Zone] = []
    for i in range(1, len(bars)):
        baseline = median(trs[max(0, i - 20) : i]) if i else 0.0
        if baseline <= 0 or trs[i] < displacement * baseline:
            continue
        direction = (
            1 if any(bars[i].close > bars[p].high for p in highs if p + span < i) else 0
        )
        direction = (
            -1
            if any(bars[i].close < bars[p].low for p in lows if p + span < i)
            else direction
        )
        opposite = next(
            (
                j
                for j in range(i - 1, -1, -1)
                if (bars[j].close < bars[j].open) == (direction == 1)
            ),
            None,
        )
        if direction and opposite is not None:
            zones.append(
                Zone(
                    "order_block", direction, bars[opposite].low, bars[opposite].high, i
                )
            )
    return zones


def _first_return(zone: Zone, bars: Sequence[Bar], index: int) -> bool:
    def touches(bar: Bar) -> bool:
        return bar.low <= zone.high and bar.high >= zone.low

    def reaches_midpoint(bar: Bar) -> bool:
        if zone.direction == 1:
            return bar.low <= zone.midpoint
        return bar.high >= zone.midpoint

    prior = sum(touches(bars[i]) for i in range(zone.created + 1, index))
    return prior == 0 and touches(bars[index]) and reaches_midpoint(bars[index])


def _sfp(bars: Sequence[Bar], index: int, span: int, direction: int) -> bool:
    highs, lows = confirmed_pivots(bars[: index + 1], span)
    bar = bars[index]
    if direction == 1 and lows:
        level = bars[lows[-1]].low
        return bar.low < level < bar.close
    if direction == -1 and highs:
        level = bars[highs[-1]].high
        return bar.high > level > bar.close
    return False


def _lvn_rejection(bars: Sequence[Bar], bins: int, quantile: float) -> bool:
    prices = [(bar.high + bar.low + bar.close) / 3.0 for bar in bars]
    lo, hi = min(prices), max(prices)
    if hi <= lo or sum(bar.volume for bar in bars) <= 0:
        return False
    volumes = [0.0] * bins
    for price, bar in zip(prices, bars, strict=True):
        idx = min(bins - 1, int((price - lo) / (hi - lo) * bins))
        volumes[idx] += max(0.0, bar.volume)
    ordered = sorted(volumes)
    threshold = ordered[min(len(ordered) - 1, int(quantile * len(ordered)))]
    current = min(bins - 1, int((prices[-1] - lo) / (hi - lo) * bins))
    return volumes[current] <= threshold and current in (0, bins - 1)


@strategies.register("institutional_price_action")
class InstitutionalPriceAction:
    """Signal uniquement; l'exécution reste hors de la stratégie."""

    name = "institutional_price_action"
    favorable_regime = "any"

    def __init__(
        self,
        pivot_span: int,
        htf_multiple: int,
        displacement_multiple: float,
        stop_buffer_bps: float,
        tp2_rr: float = 3.0,
        volume_bins: int | None = None,
        lvn_quantile: float | None = None,
    ) -> None:
        if pivot_span < 1 or htf_multiple < 2 or displacement_multiple <= 0:
            raise ValueError("calibration structurelle invalide")
        if stop_buffer_bps < 0 or tp2_rr < 3:
            raise ValueError("buffer négatif ou objectif inférieur à 3R")
        if (volume_bins is None) != (lvn_quantile is None):
            raise ValueError(
                "volume_bins et lvn_quantile doivent être fournis ensemble"
            )
        if lvn_quantile is not None and not 0 < lvn_quantile < 1:
            raise ValueError("lvn_quantile doit être dans ]0,1[")
        self.span, self.htf = pivot_span, htf_multiple
        self.displacement, self.buffer = displacement_multiple, stop_buffer_bps / 1e4
        self.rr, self.volume_bins, self.lvn_quantile = tp2_rr, volume_bins, lvn_quantile
        self.counters = {
            "candidates": 0,
            "ftb_vetoes": 0,
            "sfp_vetoes": 0,
            "volume_vetoes": 0,
            "rr_vetoes": 0,
            "signals": 0,
        }

    def _candidate(self, bars: Sequence[Bar], direction: int) -> Zone | None:
        zones = _fvg_zones(bars) + _order_blocks(bars, self.span, self.displacement)
        eligible = [
            z for z in zones if z.direction == direction and z.created < len(bars) - 1
        ]
        return max(eligible, key=lambda z: z.created, default=None)

    def guard_diagnostics(self) -> dict[str, dict[str, float | int | None]]:
        """Compteurs; chaque veto supprime 100 % du risque candidat."""
        diagnostics: dict[str, dict[str, float | int | None]] = {}
        for guard in ("ftb", "sfp", "volume", "rr"):
            count = self.counters[f"{guard}_vetoes"]
            diagnostics[guard] = {
                "triggers": count,
                "mean_risk_reduction": 1.0 if count else None,
            }
        return diagnostics

    def generate_signals(self, bars: Sequence[Bar], regime=None) -> list[Signal]:
        if len(bars) < max(3 * self.span + 2, 2 * self.htf):
            return []
        direction, transition = structure_state(
            _completed_htf(bars, self.htf), self.span
        )
        zone = self._candidate(bars, direction)
        if not direction or zone is None:
            return []
        self.counters["candidates"] += 1
        index = len(bars) - 1
        if not _first_return(zone, bars, index):
            self.counters["ftb_vetoes"] += 1
            return []
        if not _sfp(bars, index, self.span, direction):
            self.counters["sfp_vetoes"] += 1
            return []
        if self.volume_bins and not _lvn_rejection(
            bars[-100:], self.volume_bins, float(self.lvn_quantile)
        ):
            self.counters["volume_vetoes"] += 1
            return []
        signal = self._signal(bars, zone, direction, transition)
        if signal is None:
            self.counters["rr_vetoes"] += 1
            return []
        self.counters["signals"] += 1
        return [signal]

    def _signal(
        self, bars: Sequence[Bar], zone: Zone, direction: int, transition: str
    ) -> Signal | None:
        bar = bars[-1]
        entry = bar.close
        stop = (
            zone.low * (1 - self.buffer)
            if direction == 1
            else zone.high * (1 + self.buffer)
        )
        risk = abs(entry - stop)
        highs, lows = confirmed_pivots(bars, self.span)
        levels = (
            [bars[i].high for i in highs if bars[i].high > entry]
            if direction == 1
            else [bars[i].low for i in lows if bars[i].low < entry]
        )
        tp1 = (
            min(levels)
            if direction == 1 and levels
            else max(levels)
            if direction == -1 and levels
            else None
        )
        if tp1 is None or abs(tp1 - entry) < 2.0 * risk:
            return None
        target = entry + direction * self.rr * risk
        return Signal(
            bar.instrument,
            SignalDirection.LONG if direction == 1 else SignalDirection.SHORT,
            self.name,
            bar.ts,
            1.0,
            stop,
            target,
            f"HTF {transition.upper()} + {zone.kind} FTB + SFP",
            {
                "entry": entry,
                "zone_midpoint": zone.midpoint,
                "risk_per_unit": risk,
                "structure_transition": 1.0 if transition == "choch" else 0.0,
                "tp1": tp1,
                "tp2": target,
            },
        )
