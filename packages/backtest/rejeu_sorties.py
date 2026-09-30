"""Sorties (stops, prise partielle) branchées sur le REJEU de production — mesurer avant d'adopter.

La question posée : couper les pertes et encaisser une partie des gains ENTRE deux
rééquilibrages améliore-t-il le portefeuille qui trade ? La seule réponse honnête compare
les MÊMES décisions de production, simulées avec et sans sorties, sur les mêmes dates
(`comparer_sorties`) : l'écart ne peut venir que des sorties.

Trois règles de simulation, chacune pour qu'on ne mesure pas autre chose qu'une sortie :
  * exécution EN SÉANCE, avant le marquage au close : au stop, à l'ouverture sur gap
    (`sorties_suiveuses.declencher`) ;
  * CARENCE de `cooldown` séances : une ligne stoppée n'est pas rachetée par le
    rééquilibrage suivant (on mesurerait un aller-retour payé deux fois) ; après une
    prise partielle, sa cible est réduite d'autant pendant la carence ;
  * le CŒUR indiciel (QQQ) n'est jamais géré : c'est une exposition de marché voulue.

Le délai de carence (10 séances) et les réglages des règles sont des conventions
pré-enregistrées, NON calibrées (SHADOW_UNCALIBRATED). Aucun appelant en production.
"""

from __future__ import annotations

from bisect import bisect_right
from collections import Counter
from statistics import median

from packages.backtest.panel import _jour
from packages.strategies.sorties_suiveuses import (
    STATUT,
    Barre,
    EtatSortie,
    Reglages,
    avancer,
    declencher,
    ouvrir,
)

COOLDOWN = 10


def ohlc_par_jour(data: dict) -> dict[str, dict[str, Barre]]:
    """{symbole: {jour: Barre}} depuis les barres brutes (clôture > 0 seulement)."""
    out: dict[str, dict[str, Barre]] = {}
    for s, barres in data.items():
        par_jour = {}
        for b in barres or []:
            if b.close:
                c = float(b.close)
                par_jour[_jour(b)] = Barre(float(b.open or c), float(b.high or c),
                                           float(b.low or c), c)
        out[s] = par_jour
    return out


class Surveillance:
    """État de sortie de chaque ligne détenue, pour UN rejeu. Voir le docstring du module."""

    def __init__(self, regle: str, ohlc: dict, calendrier: list[str], *,
                 prise: bool = False, cooldown: int = COOLDOWN,
                 exclus: set[str] | None = None, reglages: Reglages | None = None) -> None:
        self.regle, self.prise, self.cooldown = regle, prise, cooldown
        self.reglages = reglages or Reglages()
        self.exclus = set(exclus or ())
        self._cal = calendrier
        self._jours = {s: sorted(p) for s, p in ohlc.items()}
        self._series = {s: [ohlc[s][j] for j in self._jours[s]] for s in ohlc}
        self.etats: dict[str, EtatSortie] = {}
        self.bloques: dict[str, tuple[str, float]] = {}     # sym → (dernier jour, facteur)
        self.sorties: list[dict] = []
        self.non_gerees: set[str] = set()
        self.n_suivies = 0
        self.rachats_refuses = 0

    def _passe(self, sym: str, jour: str) -> list[Barre] | None:
        """Barres ≤ `jour` si `jour` est une séance de `sym`, sinon None."""
        jours = self._jours.get(sym) or []
        i = bisect_right(jours, jour)
        if i == 0 or jours[i - 1] != jour:
            return None
        n = max(self.reglages.fenetre, self.reglages.periode_atr + 1) + 1
        return self._series[sym][max(0, i - n):i]

    def _fin_carence(self, jour: str) -> str:
        i = bisect_right(self._cal, jour) - 1 + self.cooldown
        return self._cal[min(max(i, 0), len(self._cal) - 1)]

    def declencher(self, compte, jour: str, classes: dict, frais: bool) -> None:
        """En séance, avant le marquage : exécute les stops et prises touchés ce jour."""
        from packages.backtest.preset_rejeu import _cout
        for sym in list(self.etats):
            if sym not in compte.lignes:
                self.etats.pop(sym)
                continue
            passe = self._passe(sym, jour)
            barre = passe[-1] if passe else None
            d = declencher(self.etats[sym], barre) if barre else None
            if d is None:
                continue
            motif, prix, part = d
            compte.vendre_au_prix(sym, prix, part, _cout(classes.get(sym, "equity"), frais))
            self._consigner(sym, jour, motif, prix, part)

    def _consigner(self, sym: str, jour: str, motif: str, prix: float, part: float) -> None:
        etat = self.etats[sym]
        self.sorties.append({"jour": jour, "symbole": sym, "motif": motif,
                             "prix": prix, "part": part,
                             "rendement": prix / etat.entree - 1.0})
        if motif == "prise":
            etat.prise_faite = True
            self.bloques[sym] = (self._fin_carence(jour), 1.0 - part)
        else:
            self.etats.pop(sym)
            self.bloques[sym] = (self._fin_carence(jour), 0.0)

    def filtrer(self, cible: dict, jour: str) -> dict:
        """Cible du rééquilibrage, réduite pour les lignes en carence."""
        out = dict(cible)
        for sym, (fin, facteur) in list(self.bloques.items()):
            if jour > fin:
                self.bloques.pop(sym)
                continue
            if out.get(sym, 0.0) > 0:
                out[sym] *= facteur
                self.rachats_refuses += 1
        return out

    def suivre(self, compte, jour: str) -> None:
        """Au close : ouvre l'état des nouvelles lignes, avance celui des autres."""
        for sym in list(self.etats):
            if sym not in compte.lignes:
                self.etats.pop(sym)
        for sym in compte.lignes:
            if sym in self.exclus:
                continue
            passe = self._passe(sym, jour)
            if passe is None:
                continue
            if sym in self.etats:
                avancer(self.etats[sym], passe)
                continue
            etat = ouvrir(self.regle, passe, passe[-1].close, reglages=self.reglages,
                          prise=self.prise)
            if etat is None:
                self.non_gerees.add(sym)
                continue
            self.etats[sym] = etat
            self.n_suivies += 1

    def resume(self) -> dict:
        par_motif: dict[str, list[float]] = {}
        for s in self.sorties:
            par_motif.setdefault(s["motif"], []).append(s["rendement"])
        return {"statut": STATUT, "regle": self.regle, "prise": self.prise,
                "cooldown": self.cooldown, "lignes_suivies": self.n_suivies,
                "lignes_non_gerees": len(self.non_gerees),
                "sorties": dict(Counter(s["motif"] for s in self.sorties)),
                "rendement_median": {m: round(median(v), 4) for m, v in par_motif.items()},
                "rachats_refuses": self.rachats_refuses}


def comparer_sorties(data: dict, *, regle: str, prise: bool = False, pas: int = 5,
                     params: dict | None = None, coeur: dict | None = None,
                     classes: dict | None = None, capital: float | None = None,
                     frais: bool = True, reglages: Reglages | None = None,
                     prep: tuple | None = None) -> dict:
    """Mêmes décisions de production, simulées SANS puis AVEC sorties ; ΔSharpe apparié.

    `prep` = `cibles_rejouees(...)` déjà calculé : plusieurs modes ne paient qu'une fois
    les décisions de production, qui sont la partie lente."""
    from packages.backtest.preset_rejeu import (
        CAPITAL_DEFAUT,
        _prix_par_jour,
        _stats_courbe,
        cibles_rejouees,
        comparer_sharpe,
        simuler,
    )
    prep = prep or cibles_rejouees(data, pas=pas, params=params, coeur=coeur)
    if prep is None:
        return {"available": False, "raison": "historique trop court pour rejouer"}
    cal, _, cibles = prep
    prix, kw = _prix_par_jour(data), {"capital": capital or CAPITAL_DEFAUT,
                                      "classes": classes, "frais": frais}
    sans = simuler(cibles, prix, cal, **kw)
    surv = Surveillance(regle, ohlc_par_jour(data), cal, prise=prise,
                        exclus=set(coeur or ()), reglages=reglages)
    avec = simuler(cibles, prix, cal, sorties=surv, **kw)
    if not (sans.get("available") and avec.get("available")):
        return {"available": False, "raison": "simulation indisponible"}
    for r in (sans, avec):
        r["stats"] = _stats_courbe(r["equity"])
    return {"available": True, "statut": STATUT, "sans": sans, "avec": avec,
            "delta": comparer_sharpe(sans["equity"], avec["equity"]),
            "sorties": surv.resume()}
