"""Courbes de benchmark du tableau de bord — rebasées et posées SUR LEURS DATES.

Extrait de `apps/api/snapshot.py` (04/09) en même temps que la correction de fond : le
fichier dépassait très largement la limite de 400 lignes du dépôt, et cette logique est
exactement le genre de code qu'on veut tester seul, sans construire un snapshot complet.
"""

from __future__ import annotations


def ffill(px: list) -> list[float]:
    """Anti-NaN d'AFFICHAGE : dernière valeur CONNUE (barre yfinance du jour parfois
    NaN). Report du passé seulement — jamais de valeur future, jamais de NaN servi."""
    out: list[float] = []
    last = None
    for v in px:
        if v == v and v is not None:
            last = float(v)
        if last is not None:
            out.append(last)
    return out


def bench_par_date(px: list, px_dates: list, dates: list,
                    init_cap: float) -> list | None:
    """Benchmark posé sur SES dates, puis lu au calendrier de l'equity (report)."""
    par_date = {str(d)[:10]: float(v) for d, v in zip(px_dates, px, strict=False)
                if v == v and v is not None}
    pts: list[tuple[str, float]] = []
    last = None
    for d in dates:
        j = str(d)[:10]
        if j in par_date:
            last = par_date[j]
        if last is not None:
            pts.append((j, last))
    if len(pts) < 2:
        return None
    base = pts[0][1] or 1.0
    return [{"t": d, "v": round(init_cap * v / base, 2)} for d, v in pts]


def bench_series(benches: dict, dates: list, init_cap: float) -> dict:
    """Benchmarks rebasés sur le capital initial, au calendrier de l'EQUITY.

    SIXIÈME OCCURRENCE DE L'EMPILEMENT POSITIONNEL (04/09). L'ancienne version collait
    `px[i]` sur `dates[i]` en alignant par la fin : le S&P et le Nasdaq suivent le
    calendrier des indices, l'equity celui de l'univers négociable. Un seul jour férié
    d'écart décalait TOUTE la courbe du benchmark tracée sous le portefeuille — la
    comparaison visuelle que le dashboard affiche en permanence. Mesuré sur le même
    motif côté attribution : 1,25 % de séances manquantes suffisent à ramener un bêta
    de 1,20 à 0,35.

    `benches` accepte `nom -> cours` (repli positionnel, cas des séries synthétiques
    qui n'ont pas de calendrier propre) ou `nom -> (cours, dates)` — appariés par date.
    """
    out = {}
    for name, val in benches.items():
        px, px_dates = val if isinstance(val, tuple) else (val, [])
        if not px:
            continue
        if px_dates:
            serie = bench_par_date(px, px_dates, dates, init_cap)
            if serie:
                out[name] = serie
            continue
        px = ffill(px)
        if not px:
            continue
        L = min(len(px), len(dates))
        base = px[len(px) - L] or 1.0
        out[name] = [{"t": dates[len(dates) - L + i],
                      "v": round(init_cap * px[len(px) - L + i] / base, 2)} for i in range(L)]
    return out
