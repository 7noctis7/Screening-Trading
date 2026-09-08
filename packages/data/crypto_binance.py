"""Historique OHLCV quotidien depuis Binance — la source de repli quand Yahoo se trompe.

POURQUOI CETTE SOURCE. `scripts/ingest_crypto.py` interroge Yahoo sous le symbole court
(`UNI-USD`, `ARB-USD`…). Mesuré le 09/09 par `make diag-source-crypto` : pour cinq
bases, ce symbole est occupé par un HOMONYME. La corrélation des rendements avec la
référence est de −0,08 à +0,25 sur 490 à 994 jours communs : deux séries qui ne
décrivent pas le même actif. Le nom seul ne suffit donc pas à identifier une source ;
il faut pouvoir en forcer une autre, et Binance est celle contre laquelle la mesure a
été faite.

LIMITE ASSUMÉE. Binance rend 1000 barres par appel : l'historique complet se lit par
pages successives. Il commence à la cotation de la paire sur CETTE plateforme, souvent
plus tard que l'existence du jeton. Une histoire courte et JUSTE vaut mieux qu'une
histoire longue qui décrit un autre actif.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

__all__ = ["historique", "parse_ohlcv", "url_klines"]

LIMITE = 1000                    # maximum de barres par appel (contrainte Binance)
JOUR_MS = 86_400_000
PLAFOND_PAGES = 20               # 20 000 jours : bien au-delà de toute histoire crypto

Barre = tuple[str, float, float, float, float, float]


def url_klines(base: str, depuis_ms: int, limite: int = LIMITE) -> str:
    """Endpoint klines quotidien pour `{BASE}USDT`, à partir d'un instant donné."""
    return ("https://api.binance.com/api/v3/klines"
            f"?symbol={base.upper()}USDT&interval=1d"
            f"&startTime={int(depuis_ms)}&limit={int(limite)}")


def parse_ohlcv(data: Any) -> list[Barre]:
    """Klines → [(date, open, high, low, close, volume)] trié, dédoublonné par jour.

    Format Binance : [openTime(ms), open, high, low, close, volume, closeTime, …].
    Une ligne malformée est ignorée plutôt que devinée — une barre inventée vaut moins
    qu'une barre absente.
    """
    from packages.data.crypto_history import _day
    out: dict[str, Barre] = {}
    for ligne in (data or []):
        if not isinstance(ligne, (list, tuple)) or len(ligne) < 6:
            continue
        jour = _day(ligne[0], "ms")
        try:
            o, h, b, c, v = (float(ligne[i]) for i in (1, 2, 3, 4, 5))
        except (TypeError, ValueError):
            continue
        if jour and c > 0:
            out[jour] = (jour, o, h, b, c, v)
    return [out[j] for j in sorted(out)]


def _ms(jour: str) -> int:
    from datetime import UTC, datetime
    d = datetime.fromisoformat(jour).replace(tzinfo=UTC)
    return int(d.timestamp() * 1000)


def historique(base: str, depuis: str = "2015-01-01",
               get_json: Callable[[str], Any] | None = None,
               plafond_pages: int = PLAFOND_PAGES) -> list[Barre]:
    """Historique quotidien complet, page par page. [] si la source ne répond pas.

    `get_json` est injectable pour que la pagination se teste hors ligne : c'est la
    logique d'enchaînement des pages qui peut boucler ou perdre des barres, pas le
    réseau. On avance au lendemain de la dernière barre reçue et on s'arrête dès qu'une
    page ne progresse plus — sans quoi une source qui répète la même page tournerait
    en rond jusqu'au plafond.
    """
    if get_json is None:
        from packages.data.crypto_history import _get_json
        get_json = _get_json
    curseur, barres, vues = _ms(depuis), [], set()
    for _ in range(plafond_pages):
        page = parse_ohlcv(get_json(url_klines(base, curseur)))
        nouvelles = [b for b in page if b[0] not in vues]
        if not nouvelles:
            break
        vues.update(b[0] for b in nouvelles)
        barres.extend(nouvelles)
        curseur = _ms(nouvelles[-1][0]) + JOUR_MS
        if len(page) < LIMITE:
            break
    return sorted(barres)
