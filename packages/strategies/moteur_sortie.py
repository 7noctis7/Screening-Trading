"""Moteur de SORTIE : temps, liquidité opposée, partielle sur divergence de flux.

SPÉCIFIÉ PAR L'UTILISATEUR (02/09), bloc 3. Ce bloc converge avec une mesure déjà faite
sur les données réelles de ce dépôt, et la convergence mérite d'être écrite plutôt que
présentée comme une coïncidence.

CE QUE LA MESURE DU 02/09 DIT DÉJÀ (ADR-0052, `scripts/sortie_lab.py`, 786 titres,
2,05 M de barres). Le stop suiveur a été RETIRÉ de la production après une règle écrite
d'avance : sans suiveur, payoff 3,21 · Sharpe 0,53 · maxDD -27,8 % ; avec un suiveur à
5 ATR — la configuration de production d'alors — payoff 2,82 · Sharpe 0,38 · maxDD
-29,1 %. Le mécanisme : l'avantage vit dans la QUEUE DROITE, et tout ce qui la tronque
le détruit. La cible visait +24 ATR, le suiveur mordait presque toujours avant, si bien
que le 6:1 nominal n'existait pas dans les faits.

L'INTERDICTION DU BREAKEVEN DE CONFORT DE LA SPEC EST DONC LA MÊME RÈGLE, formulée
autrement — et elle est ici l'invariant central : le stop ne bouge JAMAIS sans un nouvel
invalidant STRUCTUREL. Ni au point d'entrée, ni à un multiple d'ATR, ni après un gain.

CE QUI EST UNE APPROXIMATION, ET IL FAUT LE NOMMER. Le CVD (Cumulative Volume Delta) se
calcule sur des TRANSACTIONS signées : chaque échange classé à l'achat ou à la
vente. Des barres OHLCV n'en contiennent pas. `delta_signe` utilise donc le proxy
standard — la position de la clôture dans la barre (close location value) multipliée
par le volume. Ce proxy capte la direction dominante d'une séance ; il ne capte PAS
l'absorption au sens du carnet. Une divergence détectée ici est un fait de prix et de
volume, pas une preuve de flux institutionnel. Le nom `cvd_proxy` est là pour que
personne ne l'oublie en aval.

STATUT : SHADOW. Aucun appelant en production.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from packages.indicators.market_structure import pivots_indexes

STATUT = "SHADOW_UNCALIBRATED"

DUREE_NOMINALE_MIN = 2         # bornes NOMINALES de la fenêtre swing — voir `Position`
DUREE_MAX = 15                 # jours de bourse : sortie de temps forcée à la clôture
R_PARTIEL = 2.0                # seuil de la partielle sur divergence
PART_PARTIELLE = 0.50
R_CIBLE_MIN = 3.0
PIVOT = 5


def delta_signe(barre) -> float:
    """Volume signé approché : position de la clôture dans la barre × volume.

    `((C-L) - (H-C)) / (H-L)` vaut +1 sur une clôture au plus haut, -1 au plus bas, 0 au
    milieu. C'est le proxy usuel du delta quand on n'a pas les transactions signées — et
    ce n'en est qu'un proxy : une séance qui monte sur des ventes absorbées et une
    séance qui monte sur des achats agressifs y sont indiscernables.
    """
    h, b, c = float(barre.high), float(barre.low), float(barre.close)
    amplitude = h - b
    if amplitude <= 0:
        return 0.0
    return ((c - b) - (h - c)) / amplitude * float(barre.volume)


def cvd_proxy(barres, jusqu_a: int | None = None) -> list[float]:
    """Cumul du delta signé approché. Aucune lecture postérieure à `jusqu_a`."""
    fin = len(barres) if jusqu_a is None else jusqu_a + 1
    total, out = 0.0, []
    for b in barres[:fin]:
        total += delta_signe(b)
        out.append(total)
    return out


def divergence_baissiere(barres, i: int, pivot: int = PIVOT) -> dict:
    """Le prix fait un plus-haut que le sommet précédent, le CVD approché non.

    LES DEUX SOMMETS SONT DES PIVOTS CONFIRMÉS, jamais le plus-haut courant :
    comparer la barre du jour à un pivot confirmé reviendrait à opposer un point non
    validé à un point validé, et la divergence sortirait une séance sur deux.
    """
    ih, _ = pivots_indexes(barres, i, pivot)
    if len(ih) < 2:
        return {"divergence": False, "motif": "moins de deux sommets confirmés"}
    a, b = ih[-2], ih[-1]
    prix_a, prix_b = float(barres[a].high), float(barres[b].high)
    c = cvd_proxy(barres, i)
    if prix_b <= prix_a:
        return {"divergence": False, "motif": "pas de nouveau sommet"}
    diverge = c[b] <= c[a]
    return {"divergence": bool(diverge), "sommet_precedent": prix_a,
            "sommet_courant": prix_b, "cvd_precedent": round(c[a], 2),
            "cvd_courant": round(c[b], 2),
            "motif": "" if diverge else "le flux confirme le nouveau sommet"}


@dataclass
class Position:
    """Position OUVERTE et son état de sortie. Le stop y est le seul champ mutable.

    LA FENÊTRE NOMINALE 2-15 JOURS N'EST PAS UNE IMMOBILISATION. La borne haute est une
    règle exécutable (sortie forcée) ; la borne basse décrit l'horizon attendu, et la
    transformer en verrou empêcherait de prendre un gain que le marché offre au jour 1 —
    un coût, pas une protection. `hors_fenetre_nominale` la REPORTE, sans bloquer.
    """

    symbole: str
    sens: str
    entree: float
    stop_initial: float
    quantite: float
    index_entree: int
    stop_courant: float = 0.0
    quantite_restante: float = 0.0
    partielle_prise: bool = False
    journal: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.stop_courant == 0.0:
            self.stop_courant = self.stop_initial
        if self.quantite_restante == 0.0:
            self.quantite_restante = self.quantite
        if self.risque_unitaire <= 0:
            raise ValueError("distance entrée-stop nulle : taille non calculable")

    @property
    def risque_unitaire(self) -> float:
        """1R en unité de PRIX, fixé à l'entrée. Il ne bouge pas quand le stop bouge."""
        return abs(self.entree - self.stop_initial)

    def multiple_r(self, prix: float) -> float:
        signe = 1.0 if self.sens == "long" else -1.0
        return signe * (float(prix) - self.entree) / self.risque_unitaire


class ExitEngine:
    """Sortie de temps, cible de liquidité opposée, partielle sur divergence de flux.

    UN SEUL INVARIANT GOUVERNE TOUTE LA CLASSE : le stop ne recule jamais et ne bouge
    que sur un invalidant STRUCTUREL. Les autres règles produisent des sorties ;
    celle-ci est la seule qui protège, et la seule qu'on est tenté d'assouplir.

    L'ORDRE D'ÉVALUATION EST PESSIMISTE ET DÉLIBÉRÉ : stop, puis cible, puis temps,
    puis partielle. Quand une barre touche le stop ET la cible, on ignore laquelle est
    venue en premier — des barres quotidiennes ne le disent pas. Retenir le stop est
    l'hypothèse défavorable ; retenir la cible fabriquerait de la performance à partir
    d'une ambiguïté.
    """

    def __init__(self, duree_max: int = DUREE_MAX, r_partiel: float = R_PARTIEL,
                 part_partielle: float = PART_PARTIELLE, pivot: int = PIVOT,
                 r_cible_min: float = R_CIBLE_MIN) -> None:
        self.duree_max = duree_max
        self.r_partiel = r_partiel
        self.part_partielle = part_partielle
        self.pivot = pivot
        self.r_cible_min = r_cible_min

    def cible_liquidite(self, position: Position, barres, i: int,
                        fenetre: int = 50) -> float:
        """Cible = liquidité opposée MACRO, plancher à `r_cible_min` R.

        Les deux critères de la spec coexistent au lieu de se remplacer : le sommet
        majeur est la cible STRUCTURELLE, le multiple de R le plancher STATISTIQUE.
        Le sommet seul accepterait des trades à 1,2 R ; le R seul viserait un prix que
        rien n'attire. On garde le plus EXIGEANT des deux.
        """
        plancher = (position.entree + self.r_cible_min * position.risque_unitaire
                    if position.sens == "long"
                    else position.entree - self.r_cible_min * position.risque_unitaire)
        debut = max(0, i - fenetre)
        if i - debut < 5:
            return plancher
        if position.sens == "long":
            return max(plancher, max(float(b.high) for b in barres[debut:i]))
        return min(plancher, min(float(b.low) for b in barres[debut:i]))

    def invalidant_structurel(self, position: Position, barres, i: int) -> float | None:
        """Nouveau stop SI et SEULEMENT SI la structure en a créé un — sinon `None`.

        Pour un long : un creux confirmé PLUS HAUT que le stop courant, lui-même validé
        par un sommet confirmé POSTÉRIEUR. Les deux conditions comptent : un creux plus
        haut sans nouveau sommet derrière n'est pas une structure, c'est une pause.

        C'est ici que se joue l'interdiction du breakeven. Aucune branche de cette
        fonction ne regarde le prix d'entrée, ni le gain courant, ni un multiple d'ATR.
        """
        ih, ib = pivots_indexes(barres, i, self.pivot)
        if position.sens == "long":
            if not ib or not ih:
                return None
            creux = ib[-1]
            if not any(h > creux for h in ih):        # pas de sommet APRÈS le creux
                return None
            niveau = float(barres[creux].low)
            return niveau if niveau > position.stop_courant else None
        if not ih or not ib:
            return None
        sommet = ih[-1]
        if not any(b > sommet for b in ib):
            return None
        niveau = float(barres[sommet].high)
        return niveau if niveau < position.stop_courant else None

    def evaluer(self, position: Position, barres, i: int) -> dict:
        """Décision de sortie à la barre `i`. Ne lit jamais `barres[i+1:]`.

        Renvoie TOUJOURS la liste des règles évaluées, y compris celles qui n'ont pas
        mordu : un moteur qui n'affiche que la règle gagnante rend impossible de
        savoir laquelle a failli se déclencher.
        """
        barre = barres[i]
        jours = i - position.index_entree
        actions: list[dict] = []
        touche_stop = (float(barre.low) <= position.stop_courant
                       if position.sens == "long"
                       else float(barre.high) >= position.stop_courant)
        if touche_stop:
            actions.append(self._sortie("stop", position.stop_courant,
                                        position.quantite_restante,
                                        "invalidation structurelle atteinte"))
            return self._resultat(position, jours, actions, barre)
        cible = self.cible_liquidite(position, barres, i)
        atteint = (float(barre.high) >= cible if position.sens == "long"
                   else float(barre.low) <= cible)
        if atteint:
            actions.append(self._sortie("cible", cible, position.quantite_restante,
                                        "liquidité opposée / plancher en R"))
            return self._resultat(position, jours, actions, barre)
        if jours >= self.duree_max:
            actions.append(self._sortie("temps", float(barre.close),
                                        position.quantite_restante,
                                        f"{self.duree_max} séances sans résolution"))
            return self._resultat(position, jours, actions, barre)
        partielle = self._partielle(position, barres, i)
        if partielle:
            actions.append(partielle)
        nouveau = self.invalidant_structurel(position, barres, i)
        if nouveau is not None:
            actions.append({"type": "stop_deplace", "de": position.stop_courant,
                            "vers": nouveau, "motif": "nouvel invalidant structurel"})
        return self._resultat(position, jours, actions, barre)

    def _partielle(self, position: Position, barres, i: int) -> dict | None:
        """50 % à 2R SI ET SEULEMENT SI le flux diverge. Une seule fois par position."""
        if position.partielle_prise or position.sens != "long":
            return None
        if position.multiple_r(float(barres[i].close)) < self.r_partiel:
            return None
        d = divergence_baissiere(barres, i, self.pivot)
        if not d.get("divergence"):
            return None
        return {"type": "partielle", "prix": float(barres[i].close),
                "quantite": position.quantite_restante * self.part_partielle,
                "motif": "divergence de flux à 2R", "detail": d}

    @staticmethod
    def _sortie(type_: str, prix: float, quantite: float, motif: str) -> dict:
        return {"type": type_, "prix": float(prix), "quantite": float(quantite),
                "motif": motif}

    def _resultat(self, position: Position, jours: int, actions: list, barre) -> dict:
        return {"statut": STATUT, "symbole": position.symbole, "jours_detenus": jours,
                "hors_fenetre_nominale": jours < DUREE_NOMINALE_MIN,
                "r_courant": round(position.multiple_r(float(barre.close)), 3),
                "stop_courant": position.stop_courant, "actions": actions,
                "cloture": bool(any(a["type"] in ("stop", "cible", "temps")
                                    for a in actions))}

    def appliquer(self, position: Position, resultat: dict) -> Position:
        """Applique les actions. Le stop ne RECULE jamais, quoi qu'il arrive.

        Le garde-fou est ici ET dans `invalidant_structurel` : une règle de sécurité
        qui n'existe qu'à un seul endroit finit par être contournée par un appelant
        qui écrit le champ directement.
        """
        for a in resultat["actions"]:
            if a["type"] == "partielle":
                position.quantite_restante -= a["quantite"]
                position.partielle_prise = True
                position.journal.append(f"partielle {a['quantite']:.4f} @ {a['prix']}")
            elif a["type"] == "stop_deplace":
                vers = float(a["vers"])
                progresse = (vers > position.stop_courant if position.sens == "long"
                             else vers < position.stop_courant)
                if progresse:
                    position.stop_courant = vers
                    position.journal.append(f"stop → {vers}")
            else:
                position.quantite_restante = 0.0
                position.journal.append(f"{a['type']} @ {a['prix']}")
        return position


__all__ = ["ExitEngine", "Position", "cvd_proxy", "delta_signe", "divergence_baissiere"]
