"""Payload de la courbe de performance réelle vs références — DONNÉES RÉELLES seulement.

Ce module ne fabrique aucune série. Si une référence n'est pas dans les bases de prix
locales, elle est absente du graphe et nommée dans `ecartees` : le front affiche donc ce
qu'on a mesuré, jamais un repli synthétique. Le mandat données-réelles du dépôt interdit
qu'une courbe de performance affiche autre chose que des cours observés — un utilisateur
qui compare son compte à un indice ne peut pas deviner que l'indice a été simulé.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MARGE_AMONT = 10          # jours ouvrés de recul : la 1ʳᵉ date du PF peut être fériée


def _bases() -> list[Path]:
    """Bases de prix par priorité — la longue d'abord (cf. `fusion_sources`)."""
    from apps.api.snapshot import _price_db_path
    chemins = [_price_db_path(), ROOT / "data" / "market.db",
               ROOT / "data" / "crypto.db"]
    return [Path(c) for c in chemins if c and Path(c).exists()]


def _serie_prix(alias: str, debut: str, fin: str) -> tuple[list[str], list[float]]:
    """(dates, clôtures) fusionnées des bases pour cet alias. ([], []) si absent."""
    from packages.data.providers.db_provider import DBPriceProvider
    d0 = date.fromisoformat(debut) - timedelta(days=MARGE_AMONT)
    d1 = date.fromisoformat(fin) + timedelta(days=1)
    fusion: dict[str, float] = {}
    for base in _bases():
        try:
            barres = DBPriceProvider(base).fetch_ohlcv(alias, "1d", d0, d1)
        except Exception:  # noqa: BLE001 — une base muette n'est pas une erreur
            continue
        for b in barres:
            # `setdefault` : la PREMIÈRE base gagne, les suivantes ne comblent que les
            # dates absentes — même politique d'ajustement que le reste du dépôt.
            fusion.setdefault(str(b.ts)[:10], float(b.close))
    dates = sorted(fusion)
    return dates, [fusion[d] for d in dates]


def _reference(aliases: list[str], debut: str,
               fin: str) -> tuple[list[str], list[float]]:
    """Premier alias qui COUVRE le début du portefeuille. Les suivants ne serviraient
    à rien : une série qui commence après le premier point est écartée en aval."""
    for alias in aliases:
        dates, closes = _serie_prix(alias, debut, fin)
        if dates and dates[0] <= debut:
            return dates, closes
    return [], []


def payload() -> dict:
    """{serie, benchmarks, performances, ecartees, disponible} — tout en dollars."""
    from packages.execution.equity_history import _load
    from packages.portfolio.comparaison_benchmark import (
        REFERENCES,
        comparaison,
        serie_totale,
    )
    brut = _load()
    par_broker: dict[str, list[dict]] = {}
    for ligne in brut:
        for cle, val in ligne.items():
            if cle == "date" or val is None or float(val) <= 0:
                continue
            par_broker.setdefault(cle, []).append({"t": ligne["date"], "v": float(val)})
    serie = serie_totale(par_broker)
    if len(serie) < 2:
        return {"disponible": False, "serie": serie, "benchmarks": {},
                "performances": {}, "ecartees": [],
                "motif": "moins de deux points d'equity enregistrés : rien à comparer"}
    debut, fin = serie[0]["t"], serie[-1]["t"]
    refs = {nom: _reference(alias, debut, fin) for nom, alias in REFERENCES.items()}
    trouvees = {n: r for n, r in refs.items() if r[0]}
    res = comparaison(serie, trouvees)
    # Deux façons d'être écartée, et le front doit les distinguer d'une absence de
    # graphe : introuvable dans les bases, ou trouvée mais démarrant trop tard.
    absentes = [n for n in refs if n not in trouvees]
    return {"disponible": True, "depuis": debut, "jusqu_a": fin, **res,
            "ecartees": sorted({*absentes, *res["ecartees"]})}
