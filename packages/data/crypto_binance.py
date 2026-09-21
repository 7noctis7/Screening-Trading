"""Historique OHLCV Binance (1d/4h/1h) — la source de repli quand Yahoo se trompe.

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

INTRADAY (18/09). Le même endpoint sert 1h et 4h, gratuitement et sans clé — c'est la
raison pour laquelle la crypto passe en intraday avant les actions, où l'histoire libre
est bridée à deux ans. Seul l'intervalle et le pas du curseur changent.

LA BOUGIE EN COURS N'EST PAS UNE BOUGIE. Binance renvoie toujours la période courante,
INACHEVÉE : son plus-haut, son plus-bas et sa clôture bougeront encore. L'ingérer, c'est
écrire une barre qui se contredira à la lecture suivante — et, si une décision la lit,
c'est du look-ahead à l'échelle de la période. En quotidien le défaut passait presque
inaperçu ; en 1h il devient permanent. Le filtre est EXACT parce que Binance donne le
`closeTime` (index 6) : toute barre dont la clôture est postérieure à maintenant est
écartée. Aucune heuristique, aucune marge.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

__all__ = ["historique", "parse_ohlcv", "url_klines"]

LIMITE = 1000                    # maximum de barres par appel (contrainte Binance)
JOUR_MS = 86_400_000

# Durée d'une barre, en millisecondes : c'est le pas dont avance le curseur de page.
# Réutiliser JOUR_MS pour du 1h sauterait 23 barres sur 24, en silence.
INTERVALLES = {"1d": JOUR_MS, "4h": 4 * 3_600_000, "1h": 3_600_000}

# Plafond de pages PAR INTERVALLE : 1000 barres par page, donc 20 pages suffisent en
# quotidien mais couvrent à peine trois ans en 1h. Un plafond trop bas tronque
# l'historique SANS ERREUR — la pire façon de perdre des données.
PLAFOND_PAGES_PAR_INTERVALLE = {"1d": 20, "4h": 40, "1h": 130}
PLAFOND_PAGES = 20               # défaut historique (quotidien)

Barre = tuple[str, float, float, float, float, float]


def url_klines(base: str, depuis_ms: int, limite: int = LIMITE,
               interval: str = "1d") -> str:
    """Endpoint klines pour `{BASE}USDT`, à partir d'un instant donné."""
    if interval not in INTERVALLES:
        raise ValueError(f"intervalle non géré : {interval!r} "
                         f"(connus : {sorted(INTERVALLES)})")
    return ("https://api.binance.com/api/v3/klines"
            f"?symbol={base.upper()}USDT&interval={interval}"
            f"&startTime={int(depuis_ms)}&limit={int(limite)}")


def _horodatage(ms: int, interval: str) -> str:
    """Clé de barre : le JOUR en quotidien, l'INSTANT ISO en intraday.

    Garder la clé au jour en 1h écraserait vingt-quatre barres sur vingt-quatre et n'en
    laisserait qu'une — une perte massive et parfaitement silencieuse.
    """
    from datetime import UTC, datetime
    d = datetime.fromtimestamp(int(ms) / 1000, tz=UTC)
    return d.date().isoformat() if interval == "1d" else d.isoformat()


def _close_future(ligne, maintenant_ms: int) -> bool:
    """La barre est-elle encore OUVERTE ? `closeTime` (index 6) tranche exactement."""
    try:
        return int(ligne[6]) > maintenant_ms
    except (IndexError, TypeError, ValueError):
        return False          # closeTime illisible : on garde, et rien n'est inventé


def parse_ohlcv(data: Any, interval: str = "1d",
                maintenant_ms: int | None = None) -> list[Barre]:
    """Klines → [(horodatage, open, high, low, close, volume)] trié, dédoublonné.

    Format Binance : [openTime(ms), open, high, low, close, volume, closeTime, …].
    Une ligne malformée est ignorée plutôt que devinée — une barre inventée vaut moins
    qu'une barre absente. Et la barre EN COURS est écartée : son OHLC n'est pas encore
    fixé (cf. l'en-tête du module).
    """
    from datetime import UTC, datetime
    now = (int(datetime.now(UTC).timestamp() * 1000) if maintenant_ms is None
           else int(maintenant_ms))
    out: dict[str, Barre] = {}
    for ligne in (data or []):
        if not isinstance(ligne, (list, tuple)) or len(ligne) < 6:
            continue
        if _close_future(ligne, now):
            continue
        try:
            cle = _horodatage(ligne[0], interval)
            o, h, b, c, v = (float(ligne[i]) for i in (1, 2, 3, 4, 5))
        except (TypeError, ValueError, OSError, OverflowError):
            continue
        if cle and c > 0:
            out[cle] = (cle, o, h, b, c, v)
    return [out[j] for j in sorted(out)]


def _ms(horodatage: str) -> int:
    """ISO (jour OU instant) → millisecondes UTC. Le curseur de page s'exprime en ms."""
    from datetime import UTC, datetime
    d = datetime.fromisoformat(horodatage)
    return int((d if d.tzinfo else d.replace(tzinfo=UTC)).timestamp() * 1000)


def historique(base: str, depuis: str = "2015-01-01",
               get_json: Callable[[str], Any] | None = None,
               plafond_pages: int | None = None,
               interval: str = "1d") -> list[Barre]:
    """Historique complet, page par page. [] si la source ne répond pas.

    `get_json` est injectable pour que la pagination se teste hors ligne : c'est la
    logique d'enchaînement des pages qui peut boucler ou perdre des barres, pas le
    réseau. On avance au lendemain de la dernière barre reçue et on s'arrête dès qu'une
    page ne progresse plus — sans quoi une source qui répète la même page tournerait
    en rond jusqu'au plafond.
    """
    if interval not in INTERVALLES:
        raise ValueError(f"intervalle non géré : {interval!r}")
    if get_json is None:
        from packages.data.crypto_history import _get_json
        get_json = _get_json
    if plafond_pages is None:
        plafond_pages = PLAFOND_PAGES_PAR_INTERVALLE.get(interval, PLAFOND_PAGES)
    pas = INTERVALLES[interval]
    curseur, barres, vues = _ms(depuis), [], set()
    for _ in range(plafond_pages):
        page = parse_ohlcv(get_json(url_klines(base, curseur, interval=interval)),
                           interval)
        nouvelles = [b for b in page if b[0] not in vues]
        if not nouvelles:
            break
        vues.update(b[0] for b in nouvelles)
        barres.extend(nouvelles)
        curseur = _ms(nouvelles[-1][0]) + pas
        if len(page) < LIMITE:
            break
    return sorted(barres)
