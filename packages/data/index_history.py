"""Sélection causale d'un historique d'indice : fraîcheur avant longueur."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime

from packages.core.models import Bar

# Noms d'indices NUS — jamais des tickers réseau. Chez Yahoo un indice porte toujours
# un accent circonflexe (`^VIX`, `^GSPC`) ; la forme nue est un nommage LOCAL, celui
# sous lequel nos bases stockent la même série. L'envoyer au réseau produit au mieux du
# bruit (« $VIX: possibly delisted »), au pire une collision : un jour un titre coté
# s'appelle `DJI`, on télécharge un small-cap et on le lit comme le Dow — une erreur
# SILENCIEUSE, donc pire que l'échec bruyant qu'elle remplace.
ALIAS_LOCAUX = frozenset({"VIX", "SPX", "NDX", "DJI", "RUT", "IXIC", "GSPC"})


def interrogeables_en_ligne(aliases: Iterable[str]) -> list[str]:
    """Sous-ensemble des alias qu'un fournisseur réseau peut résoudre.

    Les proxys cotés sont CONSERVÉS : `SPY` pour `^GSPC`, `QQQ` pour `^NDX` sont de
    vrais tickers et le seul repli quand l'indice lui-même ne répond pas. Seule la
    forme nue d'un nom d'indice est écartée.
    """
    return [a for a in aliases if a not in ALIAS_LOCAUX]


@dataclass(frozen=True, slots=True)
class IndexHistory:
    alias: str
    dates: tuple[str, ...]
    closes: tuple[float, ...]
    fresh: bool


def _day(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)[:10]).date()


def merge_bars(target: dict[str, tuple[object, float]], bars: Iterable[Bar]) -> None:
    """Fusionne le MÊME symbole entre bases, par date ; le dernier provider prime."""
    for bar in bars:
        ts = bar.ts
        target[_day(ts).isoformat()] = (ts, float(bar.close))


def choose_history(
    aliases: list[str],
    histories: dict[str, dict[str, tuple]],
    end,
    *,
    min_bars: int = 250,
    freshness_days: int = 7,
) -> IndexHistory | None:
    """Choisit le premier alias frais plutôt qu'une longue série périmée."""
    end_day = _day(end)
    candidates: list[IndexHistory] = []
    for alias in aliases:
        rows = sorted(histories.get(alias, {}).items())
        if len(rows) < min_bars:
            continue
        last = _day(rows[-1][0])
        fresh = (end_day - last).days <= freshness_days
        item = IndexHistory(
            alias, tuple(d for d, _ in rows), tuple(float(v[1]) for _, v in rows), fresh
        )
        if fresh:
            return item
        candidates.append(item)
    if not candidates:
        return None
    return max(candidates, key=lambda item: (item.dates[-1], len(item.dates)))
