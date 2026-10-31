"""Compte : risque de résultats, bots tiers, comparaison de comptes, top tradés.

Extrait TEL QUEL de `apps/api/snapshot.py` le 31/10 (règle des 400 lignes par fichier) : le
texte des définitions n'a pas changé. `apps/api/snapshot.py` reste la façade et ré-exporte
chaque nom, donc `from apps.api.snapshot import X` fonctionne comme avant.
"""

from __future__ import annotations


def _earnings_risk(held: list) -> list[dict]:
    """Positions détenues dont les résultats sont imminents (risque binaire). Gate QUANT_EARNINGS=1."""
    import os
    if os.environ.get("QUANT_EARNINGS") != "1" or not held:
        return []
    try:
        from packages.strategies.earnings_blackout import flag_positions
        return flag_positions(list(held)[:25], within=7)
    except Exception:  # noqa: BLE001
        return []


def _courbes_bots_tiers() -> dict[str, list]:
    """{nom: historique d'equity RÉEL} des bots tiers configurés (« XIII indic »).

    Lecture seule, best-effort : un bot muet disparaît de la comparaison, il ne fait pas
    tomber le tableau de bord. Sans clés (build du site public), rien n'est lu."""
    try:
        from packages.execution.bots_tiers import lire_tous
        return {b["nom"]: b["history"] for b in lire_tous() if b["ok"] and b["history"]}
    except Exception:  # noqa: BLE001
        return {}


def _account_compare(alp_curve: list, cr_curve: list, sp: list, ndx: list,
                     sp_dates: list[str], ndx_dates: list[str],
                     bots: dict[str, list] | None = None) -> dict:
    """Compare les comptes RÉELS (Alpaca, Crypto/Bitmart) vs S&P 500 / Nasdaq 100, rebasés à 100 sur
    la fenêtre où des données réelles existent. Courbes réelles courtes au début (compte récent).

    `bots` : {nom: courbe} des bots TIERS (`packages/execution/bots_tiers`) — une ligne
    de comparaison de plus, au même titre qu'un indice, jamais ajoutée aux comptes."""
    import numpy as np

    def by_date(px, dates):
        return {str(d)[:10]: float(v) for d, v in zip(dates, px)}

    spd, ndxd = by_date(sp, sp_dates), by_date(ndx, ndx_dates)
    reals = {}
    if len(alp_curve) >= 2:
        reals["Alpaca (réel)"] = {str(p["t"])[:10]: p["v"] for p in alp_curve}
    if len(cr_curve) >= 2:
        reals["Crypto (réel)"] = {str(p["t"])[:10]: p["v"] for p in cr_curve}
    for nom, courbe in (bots or {}).items():
        if len(courbe) >= 2:
            reals[nom] = {str(p["t"])[:10]: p["v"] for p in courbe}
    if not reals:
        return {"available": False}
    axis = sorted(set().union(*[set(d) for d in reals.values()]))

    def stats(vals):
        v = np.asarray(vals, float)
        if v.size < 2:
            return {"return": 0.0, "cagr": 0.0, "sharpe": 0.0, "maxdd": 0.0}
        r = v[1:] / v[:-1] - 1
        tot = float(v[-1] / v[0] - 1)
        sd = float(r.std())
        mdd = float((v / np.maximum.accumulate(v) - 1).min())
        cagr = float((1 + tot) ** (252.0 / len(r)) - 1) if tot > -1 else -1.0
        return {"return": round(tot, 4), "cagr": round(cagr, 4),
                "sharpe": round(r.mean() / sd * 252 ** 0.5, 2) if sd > 0 else 0.0, "maxdd": round(mdd, 4)}

    def build(dmap):
        out, last = [], None
        for d in axis:
            if d in dmap:
                last = dmap[d]
            if last is not None:
                out.append((d, last))
        if len(out) < 2:
            return None
        base = out[0][1] or 1.0
        return [{"t": d, "v": round(100 * v / base, 2)} for d, v in out], stats([v for _, v in out])

    series, kpis = {}, []
    for name, dmap in list(reals.items()) + [("S&P 500", spd), ("Nasdaq 100", ndxd)]:
        b = build(dmap)
        if b:
            series[name], st = b
            kpis.append({"name": name, **st})
    return {"available": bool(series), "window": [axis[0], axis[-1]], "series": series, "kpis": kpis}


def _top_traded(journal, k: int) -> list[tuple[str, int]]:
    """k symboles les plus tradés (pour une matrice de corrélation lisible)."""
    counts: dict[str, int] = {}
    for t in journal.all():
        counts[t.instrument] = counts.get(t.instrument, 0) + 1
    return sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:k]
