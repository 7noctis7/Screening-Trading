"""Profil d'investisseur → contraintes chiffrées sur l'outil. Pur, déterministe, testable.

Ce module ne conseille personne. Il traduit ce que l'utilisateur déclare de SA situation en
CONTRAINTES appliquées à son propre outil : un budget de perte, des plafonds par classe d'actif,
et des bornes de déviation. La différence n'est pas rhétorique — un conseil dit « achetez ceci »,
une contrainte dit « vous avez déclaré ne pas supporter plus de 20 % de baisse, l'outil s'y tient ».

Trois principes, contre trois erreurs répandues.

1. CAPACITÉ ET TOLÉRANCE SONT DEUX CHOSES DIFFÉRENTES, et c'est la PLUS PETITE qui lie.
   La capacité est objective : horizon, besoin de liquidité, stabilité des revenus. Elle dit ce
   qu'on PEUT encaisser. La tolérance est subjective : ce qu'on DIT pouvoir supporter. Un
   questionnaire qui les mélange en un « score de risque » autorise un investisseur audacieux à
   trois ans d'horizon à prendre un risque que son horizon ne permet pas. On retient le minimum.

2. LA SORTIE EST UN BUDGET DE PERTE, PAS UNE ÉTIQUETTE. « Profil dynamique » n'est pas
   vérifiable. « Baisse maximale acceptée : 25 % » l'est — on peut la confronter au réalisé, et
   elle alimente directement `vol_target_from_drawdown` déjà présent dans le dépôt.

3. UNE ALLOCATION DOIT ÊTRE COHÉRENTE AVEC LE BUDGET QU'ELLE PRÉTEND RESPECTER. C'est ce que la
   plupart des questionnaires ne font jamais : ils produisent des poids sans vérifier que ces
   poids tiennent dans la perte annoncée. Une allocation 100 % actions ne peut pas promettre
   −15 % : les actions développées ont fait −55 % en 2008. Ici l'allocation est RÉDUITE vers le
   cash jusqu'à ce qu'elle tienne dans le budget, et l'écart est déclaré.
"""

from __future__ import annotations

from dataclasses import dataclass

# Pires baisses HISTORIQUES observées, pic à creux, par classe. Ordres de grandeur documentés,
# pas des prévisions : actions développées 2007-09, émergentes 2007-08, obligations longues
# 2020-23 (le cycle de hausse des taux), or 2011-15, crypto 2021-22.
STRESS_HISTORIQUE: dict[str, float] = {
    "actions_dev": 0.55,
    "actions_em": 0.65,
    "obligations": 0.20,
    "or": 0.45,
    "crypto": 0.85,
    "cash": 0.0,
}

# Crédit de diversification appliqué à l'estimation de perte. VOLONTAIREMENT FAIBLE : en crise,
# les corrélations convergent vers 1 — actions, émergentes, crédit et or ont chuté ensemble en
# 2008. Accorder un large crédit de diversification à un budget de perte, c'est précisément se
# tromper au moment où le budget compte. 15 % est prudent, pas généreux.
CREDIT_DIVERSIFICATION = 0.15

# Plafonds DURS par classe, non compensables. Un actif capable de faire −85 % ne se rachète pas
# par une bonne note ailleurs : c'est la distinction entre un risque de performance (compensable)
# et un risque de RUINE (jamais).
PLAFOND_DUR: dict[str, float] = {"crypto": 0.20, "actions_em": 0.30, "or": 0.20}


@dataclass(frozen=True)
class Profil:
    """Ce que l'utilisateur déclare. Aucune valeur n'est devinée à sa place."""
    horizon_annees: float
    # Baisse maximale que l'utilisateur DIT accepter (0,25 = 25 %).
    perte_max_toleree: float
    # Part du patrimoine investie ici. Un même montant n'a pas le même sens selon qu'il représente
    # 5 % ou 80 % de ce qu'on possède.
    part_du_patrimoine: float = 0.5
    # Besoin de retirer une partie du capital avant l'horizon (0 = aucun).
    besoin_liquidite: float = 0.0
    revenus_stables: bool = True
    experience_annees: float = 0.0


def capacite(p: Profil) -> float:
    """Ce que la situation PERMET d'encaisser, entre 0 et 1. Objectif, indépendant des envies.

    L'horizon domine : une baisse n'est une perte que si l'on doit vendre avant qu'elle se
    résorbe. Les marchés actions ont historiquement mis 4 à 6 ans à récupérer leurs pires
    baisses — en deçà, la capacité s'effondre, quelle que soit l'audace déclarée.
    """
    h = max(0.0, float(p.horizon_annees))
    base = 0.15 if h < 2 else 0.35 if h < 4 else 0.60 if h < 7 else 0.85 if h < 12 else 1.0
    # Un besoin de liquidité raccourcit l'horizon EFFECTIF, quelle que soit la date cible.
    base *= max(0.2, 1.0 - 1.5 * max(0.0, min(1.0, float(p.besoin_liquidite))))
    # Investir l'essentiel de son patrimoine réduit la capacité : il n'y a plus de matelas ailleurs.
    part = max(0.0, min(1.0, float(p.part_du_patrimoine)))
    base *= 1.0 - 0.35 * part
    if not p.revenus_stables:
        base *= 0.7          # sans revenus stables, une baisse peut forcer à vendre au pire moment
    return round(max(0.0, min(1.0, base)), 4)


def tolerance(p: Profil) -> float:
    """Ce que l'utilisateur DIT supporter, ramené sur la même échelle 0-1.

    Bornée à la perte déclarée : au-delà de 50 % de baisse acceptée, la déclaration cesse d'être
    informative — presque personne n'a vécu cela sans vendre. L'expérience module à la marge,
    jamais au-delà de ce qui est déclaré.
    """
    perte = max(0.0, min(1.0, float(p.perte_max_toleree)))
    t = min(1.0, perte / 0.50)
    exp = max(0.0, min(1.0, float(p.experience_annees) / 10.0))
    return round(max(0.0, min(1.0, t * (0.85 + 0.15 * exp))), 4)


def risque_retenu(p: Profil) -> dict:
    """Le MINIMUM des deux, et l'explication de qui a lié.

    C'est la règle qui protège de l'erreur la plus fréquente : laisser l'envie l'emporter sur la
    situation. Un investisseur audacieux à deux ans d'horizon reste un investisseur à deux ans.
    """
    c, t = capacite(p), tolerance(p)
    niveau = min(c, t)
    lie_par = "capacité" if c < t else "tolérance" if t < c else "les deux"
    return {"niveau": round(niveau, 4), "capacite": c, "tolerance": t, "lie_par": lie_par,
            "explication": (
                "Votre horizon et votre situation limitent le risque que vous pouvez porter, "
                "en deçà de ce que vous déclarez accepter."
                if lie_par == "capacité" else
                "Votre situation permettrait davantage, mais on s'en tient à ce que vous "
                "déclarez accepter." if lie_par == "tolérance" else
                "Situation et tolérance concordent.")}


def budget_perte(p: Profil) -> float:
    """Baisse maximale visée par l'outil (alimente `vol_target_from_drawdown`).

    Jamais au-dessus de ce que l'utilisateur déclare accepter : le budget peut être plus prudent
    que la déclaration, jamais plus audacieux.
    """
    niveau = risque_retenu(p)["niveau"]
    # 5 % de plancher (un portefeuille sans risque ne rapporte rien), 45 % de plafond.
    budget = 0.05 + niveau * 0.40
    return round(min(budget, max(0.05, float(p.perte_max_toleree))), 4)


def _normaliser(w: dict[str, float]) -> dict[str, float]:
    tot = sum(max(0.0, v) for v in w.values())
    return {k: round(max(0.0, v) / tot, 4) for k, v in w.items()} if tot > 0 else w


def perte_estimee(alloc: dict[str, float]) -> float:
    """Baisse plausible de l'allocation, à partir des pires baisses historiques par classe.

    Somme pondérée, moins un crédit de diversification volontairement faible. La somme pondérée
    suppose que toutes les crises coïncident : c'est faux en temps normal, et à peu près vrai
    quand cela compte. On préfère surestimer une perte que la découvrir.
    """
    brut = sum(STRESS_HISTORIQUE.get(k, 0.0) * max(0.0, v) for k, v in alloc.items())
    return round(brut * (1.0 - CREDIT_DIVERSIFICATION), 4)


def allocation_strategique(p: Profil) -> dict:
    """Poids de politique par classe, cohérents avec le budget de perte.

    Deux étapes, et la seconde est celle que les questionnaires oublient :
      1. des poids indicatifs tirés du niveau de risque retenu, sous plafonds DURS ;
      2. une VÉRIFICATION : si la perte estimée dépasse le budget, on désensibilise vers le cash
         jusqu'à ce qu'elle tienne. Une allocation qui ne respecte pas son propre budget n'est
         pas une allocation, c'est un vœu.
    """
    n = risque_retenu(p)["niveau"]
    brut = {
        "actions_dev": 0.20 + 0.45 * n,
        "actions_em": 0.05 * n,
        "obligations": 0.45 * (1.0 - n),
        "or": 0.05 + 0.03 * (1.0 - n),
        "crypto": 0.08 * max(0.0, n - 0.4) / 0.6 if n > 0.4 else 0.0,
        "cash": 0.05 + 0.15 * (1.0 - n),
    }
    for k, cap in PLAFOND_DUR.items():
        brut[k] = min(brut[k], cap)
    alloc = _normaliser(brut)

    budget = budget_perte(p)
    perte = perte_estimee(alloc)
    reductions = 0
    # Désensibilisation : on déplace vers le cash par pas de 5 %, en réduisant proportionnellement
    # tout le reste. Borne de sécurité pour ne jamais boucler indéfiniment.
    while perte > budget and alloc.get("cash", 0.0) < 0.95 and reductions < 40:
        risque = {k: v for k, v in alloc.items() if k != "cash"}
        tot_r = sum(risque.values())
        if tot_r <= 1e-9:
            break
        pas = min(0.05, tot_r)
        alloc = {k: (v - pas * (risque[k] / tot_r) if k != "cash" else v + pas)
                 for k, v in alloc.items()}
        perte = perte_estimee(alloc)
        reductions += 1
    alloc = _normaliser(alloc)
    return {
        "poids": alloc,
        "budget_perte": budget,
        "perte_estimee": perte_estimee(alloc),
        "desensibilisations": reductions,
        "coherente": perte_estimee(alloc) <= budget + 1e-6,
        "note": ("Allocation compatible avec la perte que vous acceptez."
                 if reductions == 0 else
                 f"Allocation réduite vers le cash ({reductions} pas) : les poids indicatifs "
                 "dépassaient la baisse que vous déclarez accepter."),
    }
