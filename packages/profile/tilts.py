"""Inclinaisons tactiques BORNÉES PAR LA PREUVE, autour de l'allocation de politique.

L'arbitrage que ce module tranche. On peut incliner un portefeuille selon le contexte macro de
deux façons :
  - affirmative : « le cycle est en expansion, on surpondère la technologie de 15 points » ;
  - bornée : « le signal existe, sa force statistique est faible, on incline de 2 points ».

La première est plus vendeuse. Elle est aussi incompatible avec ce que ce site publie deux pages
plus loin : un Sharpe déflaté proche de zéro, c'est-à-dire AUCUN alpha directionnel démontré. Un
outil qui affiche son absence de preuve puis incline de 15 points sur cette même absence se
contredit — et c'est le lecteur attentif qui le remarquera en premier.

D'où la règle : **l'amplitude de l'inclinaison est proportionnelle à la force de la PREUVE, pas
à celle du signal.** Un signal spectaculaire sans preuve statistique produit une inclinaison
quasi nulle. C'est l'inverse de l'intuition, et c'est exactement le point.

Trois garde-fous non négociables :
  1. les inclinaisons somment à zéro — on déplace du poids, on n'en crée pas ;
  2. elles ne franchissent JAMAIS les plafonds durs du profil (risque de ruine) ;
  3. elles ne dégradent jamais le budget de perte : l'allocation inclinée est revérifiée.
"""

from __future__ import annotations

from packages.profile.investor import PLAFOND_DUR, Profil, budget_perte, perte_estimee

# Amplitude MAXIMALE d'une inclinaison, en points de poids, preuve parfaite comprise. Cinq points
# sur un portefeuille est déjà une prise de position nette ; au-delà, ce n'est plus une
# inclinaison, c'est une autre stratégie — qui devrait alors être backtestée comme telle.
AMPLITUDE_MAX = 0.05

# En deçà de cette force de preuve, on n'incline pas du tout. Un signal faible n'est pas un
# petit signal : c'est du bruit, et incliner « un peu » sur du bruit coûte du frottement pour
# une espérance nulle.
PREUVE_MIN = 0.30


def force_preuve(t_stat: float | None, n_obs: int | None,
                 dsr: float | None = None) -> dict:
    """Force de la preuve, entre 0 et 1, à partir de ce qui est MESURÉ.

    Trois exigences cumulatives, parce qu'elles échouent différemment :
      - `t_stat` : le signal est-il distinguable de zéro ? En deçà de |t| = 2, non.
      - `n_obs`  : sur combien d'observations ? Un t de 3 sur 20 points ne vaut pas un t de 2,5
                   sur 500 — le premier est un accident de petit échantillon.
      - `dsr`    : le Sharpe déflaté, qui corrige le nombre d'essais. C'est le seul des trois qui
                   punit la recherche répétée jusqu'à trouver.

    Absence d'information → preuve NULLE, jamais « moyenne ». Ne pas savoir n'est pas savoir à
    moitié.
    """
    if t_stat is None or n_obs is None:
        return {"force": 0.0, "motif": "significativité non mesurée — aucune inclinaison"}
    t = abs(float(t_stat))
    n = int(n_obs)
    if n < 60:
        return {"force": 0.0, "motif": f"échantillon trop court ({n} observations)"}
    # |t| = 2 → 0 ; |t| = 4 → 1. Linéaire entre les deux, borné.
    f_t = max(0.0, min(1.0, (t - 2.0) / 2.0))
    # L'échantillon module : 60 points → moitié de crédit, 250+ → plein crédit.
    f_n = max(0.0, min(1.0, (n - 60) / 190.0)) * 0.5 + 0.5
    f = f_t * f_n
    motif = ""
    if dsr is not None:
        d = max(0.0, min(1.0, float(dsr)))
        f *= d
        if d < 0.05:
            motif = ("Sharpe déflaté quasi nul : après correction du nombre d'essais, "
                     "le signal n'est pas distinguable de la chance")
    if not motif:
        motif = ("preuve insuffisante" if f < PREUVE_MIN
                 else f"significatif (|t| = {t:.1f} sur {n} observations)")
    return {"force": round(f, 4), "motif": motif, "t_stat": round(t, 2), "n_obs": n}


def incliner(alloc: dict[str, float], vues: dict[str, float], preuve: float,
             p: Profil) -> dict:
    """Applique des inclinaisons bornées à une allocation de politique.

    `vues` = direction souhaitée par classe, dans [-1, 1] (+1 = surpondérer au maximum).
    `preuve` = force de la preuve, dans [0, 1] (cf. `force_preuve`).

    L'amplitude effective vaut `AMPLITUDE_MAX × preuve`. Sous `PREUVE_MIN`, aucune inclinaison.
    """
    base = dict(alloc)
    if preuve < PREUVE_MIN or not vues:
        return {"poids": base, "inclinaisons": {}, "amplitude": 0.0,
                "applique": False,
                "note": ("Aucune inclinaison : la preuve statistique est insuffisante. "
                         "Incliner « un peu » sur du bruit coûte du frottement pour une "
                         "espérance nulle.")}

    amplitude = AMPLITUDE_MAX * max(0.0, min(1.0, preuve))
    # Vues centrées : les inclinaisons doivent sommer à ZÉRO. On déplace du poids d'une classe
    # vers une autre ; on n'en crée pas, sinon l'exposition totale dériverait à chaque calcul.
    pertinentes = {k: max(-1.0, min(1.0, float(v))) for k, v in vues.items() if k in base}
    if not pertinentes:
        return {"poids": base, "inclinaisons": {}, "amplitude": 0.0, "applique": False,
                "note": "Aucune vue ne porte sur une classe de l'allocation."}
    moyenne = sum(pertinentes.values()) / len(pertinentes)
    centrees = {k: v - moyenne for k, v in pertinentes.items()}

    inclinaisons: dict[str, float] = {}
    for k, v in centrees.items():
        delta = amplitude * v
        cible = base[k] + delta
        # Plafond DUR du profil : jamais franchi, quelle que soit la conviction.
        plafond = PLAFOND_DUR.get(k)
        if plafond is not None:
            cible = min(cible, plafond)
        cible = max(0.0, cible)
        inclinaisons[k] = round(cible - base[k], 4)

    incline = {k: max(0.0, base[k] + inclinaisons.get(k, 0.0)) for k in base}
    # Renormalisation : les butées (plafonds, plancher à zéro) ont pu rompre la somme à 1.
    tot = sum(incline.values())
    incline = {k: round(v / tot, 4) for k, v in incline.items()} if tot > 0 else base

    # Troisième garde-fou : l'inclinaison ne doit jamais dégrader le budget de perte. Une vue
    # tactique n'a pas à consommer la marge de sécurité que le profil a fixée.
    budget = budget_perte(p)
    perte = perte_estimee(incline)
    if perte > budget + 1e-6:
        return {"poids": base, "inclinaisons": {}, "amplitude": 0.0, "applique": False,
                "note": (f"Inclinaison annulée : elle porterait la perte estimée à "
                         f"{perte:.1%}, au-delà du budget de {budget:.1%}. Une vue tactique "
                         "ne consomme pas la marge de sécurité du profil.")}

    return {"poids": incline, "inclinaisons": inclinaisons, "amplitude": round(amplitude, 4),
            "applique": any(abs(v) > 1e-6 for v in inclinaisons.values()),
            "perte_estimee": perte, "budget_perte": budget,
            "note": (f"Inclinaison de ±{amplitude*100:.1f} points au maximum, proportionnée à la "
                     "force de la preuve — pas à celle du signal.")}


def vues_depuis_regime(cycle: str | None, risk_mode: str | None) -> dict[str, float]:
    """Vues indicatives déduites du régime macro. Direction seulement, jamais l'amplitude.

    Ce module ne décide PAS de combien incliner — cela dépend de la preuve, mesurée ailleurs.
    Il dit seulement dans quel sens pencherait un régime donné, selon des régularités documentées
    (les actifs risqués souffrent en contraction, les valeurs refuges portent en Risk-Off).
    """
    c = (cycle or "").strip().lower()
    r = (risk_mode or "").strip().lower()
    vues: dict[str, float] = {}
    if c.startswith("expans"):
        vues = {"actions_dev": 0.6, "actions_em": 0.4, "obligations": -0.5, "or": -0.3}
    elif c.startswith("contract") or c.startswith("recess"):
        vues = {"actions_dev": -0.6, "actions_em": -0.8, "obligations": 0.7, "or": 0.5}
    elif c.startswith("ralent") or c.startswith("slow"):
        vues = {"actions_dev": -0.3, "actions_em": -0.5, "obligations": 0.5, "or": 0.3}
    if "off" in r:                       # Risk-Off : on renforce le penchant défensif
        for k in ("actions_dev", "actions_em", "crypto"):
            vues[k] = vues.get(k, 0.0) - 0.4
        vues["or"] = vues.get("or", 0.0) + 0.3
    return vues
