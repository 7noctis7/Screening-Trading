"""Courbe du portefeuille RÉEL face à des indices de référence, en DOLLARS.

POURQUOI EN DOLLARS ET NON EN BASE 100. La question qu'on se pose devant ce graphe n'est
pas « quel indice a fait +8 % » mais « où en serais-je si j'avais mis la même somme
ailleurs ». On replace donc chaque référence sur le capital de DÉPART du portefeuille :
la courbe se lit alors comme un montant, et l'écart entre deux courbes est un
nombre de dollars, pas un écart de pourcentages qu'il faut retraduire.

LA RÈGLE QUI PROTÈGE LA MESURE. Pour une date du portefeuille, on prend la dernière
clôture CONNUE À CETTE DATE — jamais la suivante. Le portefeuille est valorisé les jours
où le cron passe ; les actions ne cotent pas le week-end, le crypto oui. Prendre la
clôture du lundi pour un point du samedi ferait entrer dans la comparaison une
information que le samedi n'avait pas : un look-ahead, minuscule et systématique, qui
flatterait toujours la référence la plus volatile.

CE QU'ON NE FAIT PAS. Une référence dont l'historique ne couvre pas le début du
portefeuille est ÉCARTÉE, pas prolongée vers l'arrière. Une courbe qui démarre au milieu
du graphe dit la vérité ; une courbe reconstruite par report dit une performance qui n'a
pas été observée.
"""

from __future__ import annotations

from bisect import bisect_right

# Alias par référence, dans l'ordre de préférence — mêmes listes que
# `snapshot._index_series` : les indices d'abord, leur tracker coté en repli.
REFERENCES: dict[str, list[str]] = {
    "S&P 500": ["^GSPC", "SPX", "SPY"],
    "Nasdaq 100": ["^NDX", "^IXIC", "QQQ"],
    "Bitcoin": ["BTC-USD", "BTC/USD", "BTCUSD", "BTC/USDC"],
}


def serie_totale(par_broker: dict[str, list[dict]]) -> list[dict]:
    """Equity TOTALE par date, somme des comptes présents ce jour-là.

    Une date où un seul compte a un point reste publiée avec ce seul compte : l'exclure
    creuserait un trou dans la courbe là où il y a une mesure, et la lisser inventerait
    la valeur de l'autre compte.
    """
    par_date: dict[str, float] = {}
    for points in par_broker.values():
        for p in points:
            t, v = p.get("t"), p.get("v")
            if t and v is not None:
                par_date[t] = par_date.get(t, 0.0) + float(v)
    return [{"t": t, "v": round(par_date[t], 2)} for t in sorted(par_date)]


def _derniere_connue(dates: list[str], closes: list[float], jour: str) -> float | None:
    """Dernière clôture à une date ≤ `jour`. None si la série commence après."""
    i = bisect_right(dates, jour)
    return closes[i - 1] if i else None


def aligner(serie_pf: list[dict], dates: list[str], closes: list[float]) -> list[dict]:
    """Référence replacée sur le capital de départ, aux dates du portefeuille.

    Renvoie [] si la référence ne couvre pas le premier point : mieux vaut une courbe
    absente qu'une courbe qui commence par une valeur qu'on a supposée.
    """
    if not serie_pf or not dates or len(dates) != len(closes):
        return []
    base_pf = float(serie_pf[0]["v"])
    base_ref = _derniere_connue(dates, closes, serie_pf[0]["t"])
    if not base_ref or base_ref <= 0 or base_pf <= 0:
        return []
    out: list[dict] = []
    for p in serie_pf:
        px = _derniere_connue(dates, closes, p["t"])
        if px and px > 0:
            out.append({"t": p["t"], "v": round(base_pf * px / base_ref, 2)})
    return out


def performance(serie: list[dict]) -> dict:
    """Départ, arrivée, variation absolue et relative d'une courbe. {} si vide."""
    if not serie:
        return {}
    debut, fin = float(serie[0]["v"]), float(serie[-1]["v"])
    return {"debut": round(debut, 2), "fin": round(fin, 2),
            "variation": round(fin - debut, 2),
            "variation_pct": round(fin / debut - 1.0, 6) if debut > 0 else None,
            "n_points": len(serie), "du": serie[0]["t"], "au": serie[-1]["t"]}


def comparaison(serie_pf: list[dict],
                references: dict[str, tuple[list[str], list[float]]]) -> dict:
    """{serie, benchmarks, performances} — tout aligné sur les dates du portefeuille."""
    benchmarks = {nom: aligner(serie_pf, d, c) for nom, (d, c) in references.items()}
    benchmarks = {nom: s for nom, s in benchmarks.items() if s}
    perfs = {"Portefeuille": performance(serie_pf)}
    for nom, s in benchmarks.items():
        perfs[nom] = performance(s)
    return {"serie": serie_pf, "benchmarks": benchmarks, "performances": perfs,
            "ecartees": [n for n in references if n not in benchmarks]}
