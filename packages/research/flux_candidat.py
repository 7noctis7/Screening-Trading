"""Transformer un SIGNAL en FLUX DE RENDEMENTS quotidiens, sous un protocole unique.

POURQUOI UN HARNAIS PLUTÔT QUE TROIS BACKTESTS. Comparer des candidats exige qu'ils
subissent exactement le même traitement : mêmes coûts, même rythme de décision, même
convention d'exécution. Trois implémentations séparées produiraient trois biais
différents, et l'écart mesuré entre deux candidats refléterait alors leurs
implémentations autant que leurs signaux.

L'ANTI-FUITE EST STRUCTURELLE, PAS DÉCLARATIVE. La fonction de signal ne reçoit qu'une
FENÊTRE de barres passées se terminant à `t`. Elle ne peut pas voir le futur : ce n'est
pas une discipline qu'on lui demande, c'est une impossibilité d'accès. Et le rendement
capté va de `t` à `t+1` — jamais celui de la barre qui a déclenché.

CE QUE CE HARNAIS N'EST PAS. Un moteur de production : pas de stops, pas de
dimensionnement, pas de gestion de position. Il répond à UNE question — « ce signal
produit-il un flux de rendements distinct de l'existant ? » — et il ne sert qu'à ça.
Un candidat qui passe ici doit ensuite être écrit en stratégie et repasser le gate.
"""

from __future__ import annotations

COUT_BPS_DEFAUT = 5.0            # aller-retour, ordre de grandeur actions liquides
FENETRE_DEFAUT = 250
PAS_DEFAUT = 5                   # décision hebdomadaire : criblage, pas production


def flux_quotidien(data: dict, signal, fenetre: int = FENETRE_DEFAUT,
                   pas: int = PAS_DEFAUT, cout_bps: float = COUT_BPS_DEFAUT,
                   max_lignes: int = 20) -> dict:
    """Rendements quotidiens d'un portefeuille long/flat équipondéré par `signal`.

    `signal(barres)` reçoit les `fenetre` dernières barres — la dernière étant celle
    de la décision — et renvoie un booléen. Le portefeuille est reconstitué tous les
    `pas` jours et conservé entre deux décisions.

    LE COÛT EST PRÉLEVÉ SUR LA ROTATION RÉELLE, pas forfaitairement : seules les lignes
    qui ENTRENT ou SORTENT paient. Un signal stable est donc avantagé face à un signal
    nerveux, ce qui est exactement la réalité qu'on veut refléter.
    """
    symboles = [s for s, b in data.items() if b and len(b) > fenetre + 2]
    if not symboles:
        return {"available": False, "motif": "aucune série assez longue"}
    n = min(len(data[s]) for s in symboles)
    detenu: list[str] = []
    rendements: list[float] = []
    tailles: list[int] = []
    for t in range(fenetre, n - 1):
        if (t - fenetre) % pas == 0:
            choisis = [s for s in symboles if signal(data[s][t - fenetre + 1:t + 1])]
            nouveau = choisis[:max_lignes]
            rotation = len(set(nouveau) ^ set(detenu)) / max(len(nouveau) or 1, 1)
            frais = rotation * cout_bps / 10_000.0
            detenu = nouveau
        else:
            frais = 0.0
        rendements.append(_rendement_jour(data, detenu, t) - frais)
        tailles.append(len(detenu))
    if len(rendements) < 60:
        return {"available": False, "motif": f"{len(rendements)} jours — trop peu"}
    return {"available": True, "rendements": rendements,
            "n_jours": len(rendements),
            "lignes_moyen": round(sum(tailles) / len(tailles), 1),
            "part_investie": round(sum(1 for x in tailles if x) / len(tailles), 3)}


def _rendement_jour(data: dict, detenu: list[str], t: int) -> float:
    """Rendement équipondéré de t à t+1 des lignes DÉJÀ détenues à t.

    Un titre dont la barre suivante manque est retiré de la moyenne du jour plutôt que
    compté à zéro : compter zéro fabriquerait un rendement qui n'a pas eu lieu.
    """
    if not detenu:
        return 0.0
    parts = []
    for s in detenu:
        b = data.get(s)
        if not b or t + 1 >= len(b):
            continue
        p0, p1 = float(b[t].close), float(b[t + 1].close)
        if p0 > 0:
            parts.append(p1 / p0 - 1.0)
    return sum(parts) / len(parts) if parts else 0.0
