"""Banc de mesure du moteur swing ICT — traduit des PROPOSITIONS en trades vérifiables.

POURQUOI CE BANC EXISTE. `strategies/moteur_swing` produit des propositions (entrée,
stop, cible) et n'a aucun appelant : impossible de dire si la stratégie vaut quelque
chose, donc impossible de décider de la brancher. Ce module ne branche rien — il
MESURE, pour que la décision repose sur des chiffres et non sur l'élégance d'une spec.

LES TROIS RÈGLES QUI DÉCIDENT DU RÉSULTAT. Un backtest à stop/cible se truque sans le
vouloir sur trois détails ; ils sont donc explicites ici.

1. L'ENTRÉE EST UNE LIMITE, PAS UN MARCHÉ. La proposition nomme un prix d'entrée. On
   n'entre que si une barre POSTÉRIEURE le touche, au prix nommé. Entrer « au marché à
   la clôture de détection » offrirait un prix que le marché n'a pas donné, et
   transformerait chaque signal en trade — ce qui gonfle mécaniquement le nombre
   d'observations et donc la significativité apparente.

2. STOP ET CIBLE DANS LA MÊME BARRE → C'EST LE STOP. Une barre journalière ne dit pas
   l'ordre dans lequel ses extrêmes ont été atteints. Choisir la cible, c'est choisir la
   version favorable d'une information qu'on n'a pas ; sur une stratégie dont le RR est
   supérieur à 1, ce seul choix suffit à faire passer un banc du rouge au vert.

3. RÉSULTAT EN R, PAS EN DOLLARS. Un R = la distance entrée-stop. C'est la seule unité
   qui rende comparables des trades sur des actifs à volatilités différentes, et elle
   rend le banc indépendant du dimensionnement — autre question, mesurée ailleurs.
"""

from __future__ import annotations

HORIZON_DEFAUT = 40          # barres avant abandon : au-delà, la thèse d'entrée a vécu
FENETRE_FILL_DEFAUT = 5      # barres pour toucher la limite, sinon le signal est périmé


def _px(b, champ: str) -> float:
    return float(getattr(b, champ))


def simuler_trade(barres: list, i_signal: int, sens: str, entree: float, stop: float,
                  cible: float, *, horizon: int = HORIZON_DEFAUT,
                  fenetre_fill: int = FENETRE_FILL_DEFAUT) -> dict | None:
    """Un trade, du signal à sa sortie. None si la limite n'est jamais touchée.

    Le parcours commence à `i_signal + 1` : la barre du signal est celle qu'on vient
    d'observer pour décider, on ne peut pas y traiter.
    """
    risque = abs(entree - stop)
    if risque <= 0 or sens not in ("long", "short"):
        return None
    n = len(barres)
    i_entree = None
    for k in range(i_signal + 1, min(i_signal + 1 + fenetre_fill, n)):
        if _px(barres[k], "low") <= entree <= _px(barres[k], "high"):
            i_entree = k
            break
    if i_entree is None:
        return None
    sens_l = sens == "long"
    for k in range(i_entree, min(i_entree + horizon, n)):
        bas, haut = _px(barres[k], "low"), _px(barres[k], "high")
        touche_stop = bas <= stop if sens_l else haut >= stop
        touche_cible = haut >= cible if sens_l else bas <= cible
        if touche_stop:                       # règle 2 : le stop l'emporte, toujours
            return {"i_entree": i_entree, "i_sortie": k, "sortie": "stop", "r": -1.0}
        if touche_cible:
            gain = (cible - entree) if sens_l else (entree - cible)
            return {"i_entree": i_entree, "i_sortie": k, "sortie": "cible",
                    "r": round(gain / risque, 4)}
    k = min(i_entree + horizon, n) - 1
    clot = _px(barres[k], "close")
    gain = (clot - entree) if sens_l else (entree - clot)
    return {"i_entree": i_entree, "i_sortie": k, "sortie": "horizon",
            "r": round(gain / risque, 4)}


def parcourir(symbole: str, barres: list, detecter, *, depart: int = 60,
              horizon: int = HORIZON_DEFAUT,
              fenetre_fill: int = FENETRE_FILL_DEFAUT) -> list[dict]:
    """Tous les trades du moteur sur l'historique d'un actif, dans l'ordre.

    `detecter` reçoit les barres TRONQUÉES à `i` — pas l'historique complet. C'est la
    garantie structurelle contre le look-ahead : même si un détecteur lisait
    `barres[i+5]`, il ne les aurait pas. On ne fait pas confiance à la lecture du code,
    on retire l'accès.
    """
    trades: list[dict] = []
    for i in range(depart, len(barres) - 1):
        det = detecter(symbole, barres[:i + 1], i)
        for p in det.get("propositions", []):
            t = simuler_trade(barres, i, p["sens"], p["entree"], p["stop"], p["cible"],
                              horizon=horizon, fenetre_fill=fenetre_fill)
            if t:
                trades.append({**t, "symbole": symbole, "i_signal": i,
                               "scenario": p["scenario"], "sens": p["sens"],
                               "rr_vise": p["rr"]})
    return trades


def bilan(trades: list[dict]) -> dict:
    """Espérance en R, taux de réussite, et Sharpe PAR TRADE (l'unité du DSR)."""
    if not trades:
        return {"n": 0, "statut": "UNCALIBRATED (aucun trade)"}
    rs = [float(t["r"]) for t in trades]
    n = len(rs)
    moy = sum(rs) / n
    var = sum((r - moy) ** 2 for r in rs) / (n - 1) if n > 1 else 0.0
    ec = var ** 0.5
    gagnants = sum(1 for r in rs if r > 0)
    return {"n": n, "esperance_r": round(moy, 4),
            "taux_reussite": round(gagnants / n, 4),
            "ecart_type_r": round(ec, 4),
            "sharpe_par_trade": round(moy / ec, 4) if ec > 0 else None,
            "total_r": round(sum(rs), 2),
            "par_sortie": {s: sum(1 for t in trades if t["sortie"] == s)
                           for s in ("stop", "cible", "horizon")}}
