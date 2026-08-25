"""Écart de réplication entre le portefeuille MODÈLE et le compte RÉEL, et plan pour le réduire.

Le tableau « composition modèle vs réel » montrait l'écart sans jamais le CHIFFRER, et sans dire
quoi faire. Deux conséquences observées le 24/08 :

1. On lisait « P&L modèle +158 % » à côté de « P&L réel −1,1 % » sur la même ligne (QQQ) et on en
   concluait que le réel sous-performait. C'est faux : le premier est un cumul depuis l'ouverture
   de la position dans le backtest (des années), le second depuis l'achat chez le courtier
   (des semaines). Deux durées différentes ne se comparent pas — d'où `depuis`/`jours` désormais
   publiés à côté de chaque P&L (cf. `preset_ledger`).

2. La vraie divergence n'est pas une différence de performance, c'est une différence de
   COMPOSITION : une seule ligne commune (le cœur indiciel), un satellite modèle de treize actions
   absent du compte, et une poche crypto d'environ 30 % que le modèle ne détient pas. Tant que
   cette poche existe, aucun réglage d'exécution ne rapprochera les deux courbes.

La mesure retenue est l'ACTIVE SHARE (Cremers-Petajisto, 2009) : ½·Σ|w_modèle − w_réel|. C'est la
part du portefeuille qui ne réplique PAS le modèle. Elle se lit directement : 30 % d'active share
signifie que 30 % du capital suit autre chose, et que l'écart de performance futur viendra de là.

Le plan de convergence tient compte du plancher de ligne (`QUANT_MIN_POSITION`) : une cible du
modèle qui tomberait sous le plancher n'est pas réplicable à cette taille de compte. On ne
l'ouvre pas, et on redistribue son poids au prorata des lignes réplicables — ce qui conserve
EXACTEMENT les proportions relatives du modèle (mise à l'échelle L1) au lieu de laisser dériver
du cash. La poche hors modèle n'est JAMAIS soldée d'office : c'est une décision d'argent réel,
elle appartient à l'utilisateur.
"""

from __future__ import annotations

from dataclasses import dataclass

from packages.execution.rebalance_plan import Intention, decider, min_ligne

BANDE_DEFAUT_PCT = 0.005        # 0,5 % de l'equity : sous cet écart, l'aller-retour ne se paie pas


def cle(symbole: str) -> str:
    """Clé d'appariement : BTC/USD, BTC-USD, BTCUSDT et BTCUSD sont la même exposition.

    Même normalisation que l'affichage — sinon la table dit « réel seul » pour une ligne que le
    plan considère appariée, et les deux se contredisent à l'écran."""
    s = (symbole or "").upper().replace("/", "").replace("-", "")
    for suff in ("USDT", "USDC", "USD"):
        if s.endswith(suff) and len(s) > len(suff):
            return s[: -len(suff)]
    return s


def poids(positions: list[dict], champ: str) -> dict[str, float]:
    """Poids par clé normalisée. Les montants ne sont jamais comparés : seuls les poids le sont."""
    vals = {}
    for p in positions or []:
        v = float(p.get(champ) or 0.0)
        if v > 0:
            vals[cle(p.get("symbol", ""))] = vals.get(cle(p.get("symbol", "")), 0.0) + v
    tot = sum(vals.values())
    return {k: v / tot for k, v in vals.items()} if tot > 0 else {}


def active_share(wm: dict[str, float], wr: dict[str, float]) -> float:
    """Part du capital qui ne réplique pas le modèle (Cremers-Petajisto 2009). 0 = réplication
    parfaite, 1 = aucun recouvrement."""
    return round(0.5 * sum(abs(wm.get(k, 0.0) - wr.get(k, 0.0)) for k in set(wm) | set(wr)), 4)


@dataclass(frozen=True)
class LigneEcart:
    symbole: str
    w_modele: float | None
    w_reel: float | None
    statut: str          # "commune" | "modele_seul" | "hors_modele"

    @property
    def ecart(self) -> float:
        return (self.w_reel or 0.0) - (self.w_modele or 0.0)


def ecarts(modele: list[dict], reel: list[dict], *, champ_modele: str = "value",
           champ_reel: str = "market_value") -> list[LigneEcart]:
    """Ligne à ligne, en poids. Trié par contribution à l'écart — le plus gros écart d'abord."""
    wm, wr = poids(modele, champ_modele), poids(reel, champ_reel)
    noms = {cle(p.get("symbol", "")): p.get("symbol", "") for p in (modele or []) + (reel or [])}
    out = []
    for k in set(wm) | set(wr):
        a, b = wm.get(k), wr.get(k)
        statut = "commune" if a and b else ("modele_seul" if a else "hors_modele")
        out.append(LigneEcart(noms.get(k, k), a, b, statut))
    return sorted(out, key=lambda ligne: -abs(ligne.ecart))


def _cibles_replicables(wm: dict[str, float], equity: float,
                        plancher: float) -> tuple[dict[str, float], list[str]]:
    """Poids modèle restreints aux lignes que le compte peut réellement porter.

    Une ligne à 0,3 % sur un compte de 100 000 $ vaut 300 $ : sous un plancher à 1 000 $, elle
    n'a pas sa place — l'ouvrir créerait la poussière que le plancher existe pour empêcher.
    On la retire et on remet son poids au prorata sur les autres."""
    gardees = {k: w for k, w in wm.items() if w * equity >= plancher}
    ecartees = [k for k in wm if k not in gardees]
    tot = sum(gardees.values())
    return ({k: w / tot for k, w in gardees.items()} if tot > 0 else {}), ecartees


def plan_convergence(modele: list[dict], reel: list[dict], equity: float, *,
                     bande_pct: float = BANDE_DEFAUT_PCT, plancher: float | None = None,
                     liquider_hors_modele: bool = False,
                     champ_modele: str = "value",
                     champ_reel: str = "market_value") -> dict:
    """Ordres à passer pour rapprocher le compte réel du modèle, et ce que ça change.

    `liquider_hors_modele=False` (défaut) : la poche hors modèle est CONSERVÉE et seulement
    signalée. Solder d'office une poche crypto en plus-value serait une décision fiscale et
    directionnelle prise à la place de l'utilisateur.
    """
    equity = max(0.0, float(equity))
    plancher = min_ligne() if plancher is None else float(plancher)
    bande = max(0.0, bande_pct) * equity
    wm, wr = poids(modele, champ_modele), poids(reel, champ_reel)
    as_avant = active_share(wm, wr)

    cibles_w, non_replicables = _cibles_replicables(wm, equity, plancher)
    hors = {k: w for k, w in wr.items() if k not in wm}
    poche_hors = round(sum(hors.values()), 4)

    # Le capital réellement allouable au modèle : tout, sauf la poche qu'on choisit de garder.
    part_modele = 1.0 if liquider_hors_modele else max(0.0, 1.0 - poche_hors)
    cibles = {k: w * part_modele * equity for k, w in cibles_w.items()}
    detenus = {k: w * equity for k, w in wr.items()}
    if not liquider_hors_modele:
        for k in hors:                      # hors modèle conservé → cible = détenu, aucun ordre
            cibles[k] = detenus[k]

    intentions: dict[str, Intention] = {}
    for k in sorted(set(cibles) | set(detenus)):
        intentions[k] = decider(cibles.get(k, 0.0), detenus.get(k, 0.0), bande, plancher)

    noms = {cle(p.get("symbol", "")): p.get("symbol", "") for p in (modele or []) + (reel or [])}
    ordres = [{"symbole": noms.get(k, k), "action": i.action, "montant": round(i.montant, 2),
               "liquidation": i.liquidation, "motif": i.motif,
               "poids_actuel": round(wr.get(k, 0.0), 4),
               "poids_cible": round(cibles.get(k, 0.0) / equity, 4) if equity else None}
              for k, i in intentions.items() if i.agit]

    # Active share APRÈS exécution du plan (cibles atteintes, poche conservée le cas échéant).
    wr_apres = {k: (cibles.get(k, 0.0) / equity if equity else 0.0) for k in set(cibles)}
    as_apres = active_share(wm, {k: v for k, v in wr_apres.items() if v > 0})

    return {"available": bool(wm) and equity > 0,
            "active_share_avant": as_avant, "active_share_apres": as_apres,
            "poche_hors_modele": poche_hors,
            "non_replicables": [noms.get(k, k) for k in non_replicables],
            "plancher": plancher, "bande": round(bande, 2), "equity": round(equity, 2),
            "n_ordres": len(ordres), "ordres": ordres,
            "plancher_bloquant": bool(non_replicables),
            "limite_structurelle": round(poche_hors, 4) if not liquider_hors_modele else 0.0}
