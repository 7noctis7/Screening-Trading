"""Transformer un SIGNAL en FLUX DE RENDEMENTS quotidiens, sous un protocole unique.

POURQUOI UN HARNAIS PLUTÔT QUE TROIS BACKTESTS. Comparer des candidats exige qu'ils
subissent exactement le même traitement : mêmes coûts, même rythme de décision, même
convention d'exécution. Trois implémentations séparées produiraient trois biais
différents, et l'écart mesuré entre deux candidats refléterait alors leurs
implémentations autant que leurs signaux.

L'AXE EST UN CALENDRIER, PAS UNE POSITION. Première version de ce fichier : l'axe était
`min(len(série))`, donc TOUT était tronqué à la série la plus courte de l'univers. Avec
une fenêtre de 250 barres et un titre n'en ayant que 265, il ne restait que 14 jours de
mesure — quelle que soit la profondeur des 785 autres. Les quatre candidats sont sortis
« trop peu de jours » et le banc ne mesurait rien. C'est l'empilement POSITIONNEL,
troisième occurrence dans ce dépôt après `sector_momentum` et le preset. On indexe donc
par DATE : chaque titre est lu à sa propre position pour la date du jour, et un titre
absent ce jour-là est écarté de la moyenne — jamais compté zéro.

L'ANTI-FUITE EST STRUCTURELLE, PAS DÉCLARATIVE. La fonction de signal ne reçoit qu'une
FENÊTRE de barres passées se terminant à la date de décision. Elle ne peut pas voir le
futur : ce n'est pas une discipline qu'on lui demande, c'est une impossibilité d'accès.
Et le rendement capté va d'une date à la suivante — jamais celui de la barre qui a
déclenché le signal.

CE QUE CE HARNAIS N'EST PAS. Un moteur de production : pas de stops, pas de
dimensionnement, pas de gestion de position. Il répond à UNE question — « ce signal
produit-il un flux de rendements distinct de l'existant ? » — et il ne sert qu'à ça.
Un candidat qui passe ici doit ensuite être écrit en stratégie et repasser le gate.
"""

from __future__ import annotations

COUT_BPS_DEFAUT = 5.0            # aller-retour, ordre de grandeur actions liquides
FENETRE_DEFAUT = 250
PAS_DEFAUT = 5                   # décision hebdomadaire : criblage, pas production
MIN_JOURS = 60


def _jour(ts):
    return ts.date() if hasattr(ts, "date") else ts


def _index_par_date(data: dict) -> dict:
    """{symbole: {date: position}} — la position d'un titre lui est propre."""
    return {s: {_jour(b.ts): i for i, b in enumerate(barres)}
            for s, barres in data.items() if barres}


def _calendrier(data: dict) -> list:
    """Union TRIÉE de toutes les dates. Prendre l'intersection reviendrait à ne garder
    que les jours où le titre le plus jeune cotait — la troncature qu'on corrige."""
    vues = set()
    for barres in data.values():
        vues.update(_jour(b.ts) for b in barres)
    return sorted(vues)


def flux_quotidien(data: dict, signal, fenetre: int = FENETRE_DEFAUT,
                   pas: int = PAS_DEFAUT, cout_bps: float = COUT_BPS_DEFAUT,
                   max_lignes: int = 20) -> dict:
    """Rendements quotidiens d'un portefeuille long/flat équipondéré par `signal`.

    `signal(barres, symbole)` reçoit les `fenetre` dernières barres du titre — la
    dernière étant celle de la date de décision — et renvoie un booléen. Le symbole est
    passé pour qu'un candidat coûteux puisse PRÉCALCULER sa réponse par titre au lieu de
    tout recalculer à chaque appel ; il ne donne aucun accès supplémentaire aux données.
    Le portefeuille est reconstitué tous les `pas` jours, conservé entre deux fois.

    LE COÛT EST PRÉLEVÉ SUR LA ROTATION RÉELLE, pas forfaitairement : seules les lignes
    qui ENTRENT ou SORTENT paient. Un signal stable est donc avantagé face à un signal
    nerveux, ce qui est exactement la réalité qu'on veut refléter.
    """
    if not data:
        return {"available": False, "motif": "univers vide"}
    idx = _index_par_date(data)
    axe = _calendrier(data)
    if len(axe) < fenetre + MIN_JOURS:
        return {"available": False,
                "motif": f"{len(axe)} dates au calendrier — trop peu"}
    detenu: list[str] = []
    rendements, tailles, dates = [], [], []
    for k in range(fenetre, len(axe) - 1):
        d, suivante = axe[k], axe[k + 1]
        if (k - fenetre) % pas == 0:
            choisis = _selection(data, idx, d, fenetre, signal)
            nouveau = choisis[:max_lignes]
            rotation = len(set(nouveau) ^ set(detenu)) / max(len(nouveau) or 1, 1)
            frais = rotation * cout_bps / 10_000.0
            detenu = nouveau
        else:
            frais = 0.0
        rendements.append(_rendement_jour(data, idx, detenu, d, suivante) - frais)
        tailles.append(len(detenu))
        dates.append(suivante)          # le rendement est DATÉ du jour où il se réalise
    if len(rendements) < MIN_JOURS:
        return {"available": False, "motif": f"{len(rendements)} jours — trop peu"}
    return {"available": True, "rendements": rendements, "dates": dates,
            "n_jours": len(rendements),
            "lignes_moyen": round(sum(tailles) / len(tailles), 1),
            "part_investie": round(sum(1 for x in tailles if x) / len(tailles), 3)}


def _selection(data: dict, idx: dict, d, fenetre: int, signal) -> list[str]:
    """Titres dont le signal est vrai à la date `d`, chacun lu à SA position."""
    retenus = []
    for s, positions in idx.items():
        i = positions.get(d)
        if i is None or i < fenetre - 1:          # pas coté ce jour, ou trop jeune
            continue
        if signal(data[s][i - fenetre + 1:i + 1], s):
            retenus.append(s)
    return retenus


def _rendement_jour(data: dict, idx: dict, detenu: list[str], d, suivante) -> float:
    """Rendement équipondéré de `d` à `suivante` des lignes DÉJÀ détenues.

    Un titre qui ne cote pas l'une des deux dates est retiré de la moyenne du jour
    plutôt que compté à zéro : compter zéro fabriquerait un rendement qui n'a pas eu
    lieu — la règle posée le 01/09 sur l'intégrité des séries.
    """
    if not detenu:
        return 0.0
    parts = []
    for s in detenu:
        i0, i1 = idx[s].get(d), idx[s].get(suivante)
        if i0 is None or i1 is None:
            continue
        p0, p1 = float(data[s][i0].close), float(data[s][i1].close)
        if p0 > 0:
            parts.append(p1 / p0 - 1.0)
    return sum(parts) / len(parts) if parts else 0.0
