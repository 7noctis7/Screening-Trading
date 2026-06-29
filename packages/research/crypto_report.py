"""Générateur de rapport crypto — DÉTERMINISTE (aucun texte inventé).

Transforme les métriques on-chain (DD-ATH, momentum, turnover, float, TVL/MCap) en un
rapport scannable : Flash Data + sentiment 🟢/🔴/🟡 + 3 sections (décryptage / Œil de
Hasheur / vigilance). Chaque phrase est paramétrée par les CHIFFRES réels — pas de LLM,
pas de hype. C'est du CONTEXTE, pas un signal (le gate placebo a recalé tvl/fees_mcap).
"""

from __future__ import annotations


def _median(xs: list[float]) -> float | None:
    ys = sorted(x for x in xs if x is not None)
    if not ys:
        return None
    n = len(ys)
    return ys[n // 2] if n % 2 else (ys[n // 2 - 1] + ys[n // 2]) / 2


def _vals(coins: dict, key: str):
    return [(s, d.get(key)) for s, d in coins.items() if d.get(key) is not None]


def sentiment(coins: dict) -> str:
    """🟢 BULLISH / 🔴 BEARISH / 🟡 NEUTRE — règles sur momentum + drawdown médians."""
    mom = _median([d.get("mom_30d") for d in coins.values()])
    dd = _median([d.get("dd_ath") for d in coins.values()])
    if mom is None:
        return "NEUTRE"
    if mom < -0.03 and (dd is None or dd < -0.4):
        return "BEARISH"
    if mom > 0.05:
        return "BULLISH"
    return "NEUTRE"


def _pct(x) -> str:
    return f"{x * 100:+.0f}%" if isinstance(x, (int, float)) else "—"


def generate(coins: dict, eth_ctx: dict | None = None) -> dict:
    """Rapport complet {available, sentiment, flash, decryptage, hasheur, vigilance}."""
    coins = {s: d for s, d in (coins or {}).items() if d}
    if len(coins) < 2:
        return {"available": False}
    senti = sentiment(coins)
    n = len(coins)
    med_dd = _median([d.get("dd_ath") for d in coins.values()])
    med_mom = _median([d.get("mom_30d") for d in coins.values()])

    flash = {
        "BEARISH": (f"Capitulation : {n} actifs à DD médian {_pct(med_dd)} vs ATH, "
                    f"momentum 30j médian {_pct(med_mom)}. Le marché purge levier "
                    "et unlocks."),
        "BULLISH": (f"Reprise en cours : momentum 30j médian {_pct(med_mom)} sur {n} "
                    "actifs, l'activité on-chain repart."),
        "NEUTRE": (f"Consolidation : {n} actifs, momentum médian {_pct(med_mom)}, "
                   "pas de direction tranchée."),
    }[senti]

    decryptage: list[str] = []
    tm = _vals(coins, "tvl_mcap")
    if tm:
        hi = max(tm, key=lambda x: x[1])
        lo = min(tm, key=lambda x: x[1])
        decryptage.append(
            f"TVL/MCap = le discriminant : {hi[0]} la mieux adossée ({hi[1]:.2f}), "
            f"{lo[0]} la moins ({lo[1]:.2f}) → downside plus logique côté {lo[0]}.")
    fl = _vals(coins, "float_ratio")
    if fl:
        lof = min(fl, key=lambda x: x[1])
        if lof[1] < 0.6:
            decryptage.append(
                f"{lof[0]} : float {lof[1]:.2f} → {(1 - lof[1]) * 100:.0f}% verrouillé "
                "= valeur diluée par les unlocks.")
    tu = _vals(coins, "turnover")
    if tu:
        hit = max(tu, key=lambda x: x[1])
        decryptage.append(
            f"{hit[0]} : turnover le plus élevé ({hit[1]:.3f}) = mains spéculatives ; "
            "en bear, fort turnover = distribution, pas accumulation.")

    backed = [s for s, d in coins.items() if d.get("tvl_mcap")]
    promises = [s for s, d in coins.items() if not d.get("tvl_mcap")]
    hasheur = []
    if backed:
        hasheur.append(f"Usage réel (TVL/fees mesurables) : {', '.join(backed)}. "
                       "Le marché les sanctionne moins fort sur la durée.")
    if promises:
        hasheur.append(f"Paris sur l'usage FUTUR : {', '.join(promises)}. "
                       "En bear, le marché ne paie plus les promesses.")
    if "ONDO" in coins:
        hasheur.append("RWA (type ONDO) : la TradFi migre en coulisses (Treasuries "
                       "tokenisés). C'est du cash-management institutionnel, pas de la "
                       "spéculation — le rail compte plus que le token.")

    vigilance = []
    if fl:
        lof = min(fl, key=lambda x: x[1])
        if lof[1] < 0.6:
            vigilance.append(f"Unlocks : acheter {lof[0]} (float {lof[1]:.2f}) en bear "
                             "= se positionner face à un calendrier de dilution.")
    if "ONDO" in coins:
        vigilance.append("RWA = risque de CONTREPARTIE (custodian + émetteur), pas du "
                         "collatéral trustless. Custodian KO → TVL fictive.")
    vigilance.append("Risque > conviction : positions petites, pas de levier (paper "
                     "par défaut). Contexte, pas un conseil.")

    out = {"available": True, "sentiment": senti, "flash": flash,
           "decryptage": decryptage, "hasheur": hasheur, "vigilance": vigilance}
    if eth_ctx and eth_ctx.get("available"):
        out["eth_context"] = eth_ctx
    return out
