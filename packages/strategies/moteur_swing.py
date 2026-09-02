"""Moteur swing : `MarketStructureEngine` et `RiskManager`, sur l'existant du dépôt.

SPÉCIFIÉ PAR L'UTILISATEUR (02/09). Ces deux classes n'implémentent presque rien
elles-mêmes : elles ORCHESTRENT des briques déjà écrites et déjà testées. C'est
délibéré, et c'est la règle du dépôt (CLAUDE.md) : une nouvelle stratégie se compose,
elle ne réécrit pas le cœur. Chaque bloc de la spec est donc câblé, pas recodé.

  spec                              → ce qui l'exécute
  ─────────────────────────────────────────────────────────────────────────────────
  1W Hurst > 0,55                   → `regime/hurst.hurst_rs`
  1D SFP (BSL/SSL + volume 1,5×)    → `indicators/liquidite_ict.sfp`
  1D BOS / OTE / order block        → `indicators/liquidite_ict`
  1H CHoCH (raffinement d'entrée)   → `indicators/liquidite_ict.choch`
  SL = entrée ± 2×ATR14             → `risk/atr_stops`, ici en pur Python
  1R = 1 % et descente −4R          → `risk/ddm.MachineDDM` (spécifié le 01/09)
  taille = risque / distance stop   → `risk/ddm.taille_position`
  MM200 marché + corrélation 30 j   → `risk/garde_swing`
  Ulcer, TID, R², ES Cornish-Fisher → `portfolio/metriques_survie`
  filtre ML + IC + OOS/IS           → `ml/` (cpcv, promotion, governance) + features

CE QUE CE MOTEUR NE PEUT PAS FAIRE AUJOURD'HUI, ET IL FAUT LE DIRE AVANT DE L'UTILISER.
La base de ce dépôt est QUOTIDIENNE : onze ans de barres 1D, aucune barre 1H ni 4H. La
jambe de raffinement de la spec est donc CÂBLÉE mais NON MESURABLE — `raffiner_entree`
accepte des barres intraday si on lui en fournit, et refuse explicitement de conclure
quand il n'y en a pas. Elle ne renvoie jamais un « prêt » par défaut : sans donnée, la
réponse est « indécidable », pas « oui ».

ET CE QU'AUCUNE DE CES CLASSES NE PROUVE. Elles produisent des propositions d'entrée et
des tailles de position. Elles ne démontrent aucune espérance positive : c'est le rôle
des bancs (`scripts/candidats_lab.py`, `make labs`) et de la porte de certification
(`vault/15_CERTIFICATION.md`). Une géométrie qui se code proprement n'est pas une
géométrie qui gagne.

STATUT : SHADOW. Aucun appelant en production.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from packages.indicators.liquidite_ict import choch, continuation_ote, sfp
from packages.risk.ddm import MachineDDM, taille_position
from packages.risk.garde_swing import exposition_autorisee, regime_marche

STATUT = "SHADOW_UNCALIBRATED"

HURST_PERSISTANT = 0.55
K_ATR_STOP = 2.0
PERIODE_ATR = 14
RR_MINIMUM = 3.0


def _atr(barres, periode: int = PERIODE_ATR) -> float | None:
    """ATR de Wilder à la DERNIÈRE barre, en pur Python (aucune dépendance pandas).

    `risk/atr_stops` fait le même calcul sur un DataFrame ; ce moteur travaille sur
    des listes de barres, et convertir en DataFrame à chaque titre et à chaque date
    coûterait bien plus que les quinze lignes ci-dessous.
    """
    if len(barres) < periode + 1:
        return None
    trs = []
    for i in range(1, len(barres)):
        h, b = float(barres[i].high), float(barres[i].low)
        pc = float(barres[i - 1].close)
        trs.append(max(h - b, abs(h - pc), abs(b - pc)))
    valeur = sum(trs[:periode]) / periode
    for tr in trs[periode:]:
        valeur = (valeur * (periode - 1) + tr) / periode
    return valeur if valeur > 0 else None


def _rendements(barres) -> list[float]:
    c = [float(b.close) for b in barres if float(b.close) > 0]
    return [c[i] / c[i - 1] - 1.0 for i in range(1, len(c))]


@dataclass(frozen=True)
class Proposition:
    """Une entrée PROPOSÉE — jamais un ordre. La convertir est une décision."""

    symbole: str
    scenario: str
    sens: str
    entree: float
    stop: float
    cible: float
    rr: float
    motifs: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"statut": STATUT, "symbole": self.symbole, "scenario": self.scenario,
                "sens": self.sens, "entree": round(self.entree, 6),
                "stop": round(self.stop, 6), "cible": round(self.cible, 6),
                "rr": round(self.rr, 2), "motifs": self.motifs}


class MarketStructureEngine:
    """Détection SFP et BOS/OTE en 1D, filtre de persistance en 1W, raffinement en 1H.

    LES TROIS UNITÉS DE TEMPS NE SONT PAS SUR LE MÊME PLAN, et les confondre est
    l'erreur qui rend ce genre de système illisible : la 1W AUTORISE (filtre), la 1D
    DÉCIDE (signal), la 1H PLACE (exécution). Une unité de temps qui déciderait à deux
    niveaux ferait dépendre le résultat de l'ordre d'évaluation.
    """

    def __init__(self, pivot: int = 5, fenetre_liquidite: int = 50,
                 hurst_min: float = HURST_PERSISTANT, k_atr: float = K_ATR_STOP,
                 rr_min: float = RR_MINIMUM) -> None:
        self.pivot = pivot
        self.fenetre_liquidite = fenetre_liquidite
        self.hurst_min = hurst_min
        self.k_atr = k_atr
        self.rr_min = rr_min

    def persistance(self, barres_hebdo, fenetre: int = 100) -> dict:
        """Filtre 1W : l'actif est-il en régime de PERSISTANCE (Hurst > seuil) ?

        Le Hurst est renvoyé avec son statut, jamais réduit à un booléen : sur moins de
        64 points `hurst_rs` répond UNCALIBRATED, et transformer cette absence en
        « False » ferait passer un manque de données pour une mesure défavorable.
        """
        from packages.regime.hurst import hurst_rs
        r = hurst_rs(_rendements(barres_hebdo[-fenetre:] if fenetre else barres_hebdo))
        if not r.get("available"):
            return {"disponible": False, "autorise": False,
                    "motif": "Hurst non calculable (< 64 points) — indécidable"}
        return {"disponible": True, "hurst": r["hurst"],
                "autorise": r["hurst"] > self.hurst_min,
                "motif": "" if r["hurst"] > self.hurst_min
                         else f"Hurst {r['hurst']:.3f} <= {self.hurst_min}"}

    def detecter(self, symbole: str, barres_1d: list, i: int | None = None) -> dict:
        """Scénarios A (SFP) et B (continuation OTE) sur la barre `i` du 1D.

        Les deux sont évalués et rendus ENSEMBLE. Choisir ici lequel prime cacherait le
        cas le plus instructif : celui où ils se contredisent (un SFP short pendant une
        continuation haussière), qui doit remonter au décideur, pas être arbitré ici.
        """
        i = len(barres_1d) - 1 if i is None else i
        a = sfp(barres_1d, i, fenetre=self.fenetre_liquidite)
        b = continuation_ote(barres_1d, i, pivot=self.pivot)
        propositions = []
        if a.get("sfp"):
            p = self._proposition_sfp(symbole, barres_1d, i, a)
            if p:
                propositions.append(p)
        if b.get("autorise"):
            p = self._proposition_ote(symbole, barres_1d, i, b)
            if p:
                propositions.append(p)
        return {"statut": STATUT, "sfp": a, "continuation": b,
                "propositions": [p.as_dict() for p in propositions],
                "contradiction": bool(a.get("sfp") and b.get("autorise")
                                      and a.get("sens") != b.get("sens"))}

    def _proposition_sfp(self, symbole, barres, i, det) -> Proposition | None:
        """Scénario A : stop DERRIÈRE la mèche de capture, pas à un ATR arbitraire.

        Le SFP a un invalidant naturel — l'extrême que la mèche vient de balayer. On y
        ajoute une marge d'un demi-ATR pour ne pas coller le stop au tick exact, qui est
        précisément le prix que le marché vient de venir chercher.
        """
        a = _atr(barres[:i + 1], PERIODE_ATR)
        if a is None:
            return None
        entree = float(barres[i].close)
        marge = 0.5 * a
        if det["sens"] == "long":
            stop = float(det["extreme"]) - marge
            cible = entree + self.rr_min * (entree - stop)
        else:
            stop = float(det["extreme"]) + marge
            cible = entree - self.rr_min * (stop - entree)
        return self._verifier(symbole, "SFP", det["sens"], entree, stop, cible,
                              {"niveau_balaye": det["niveau"], "atr": round(a, 6)})

    def _proposition_ote(self, symbole, barres, i, det) -> Proposition | None:
        """Scénario B : ordre LIMITE au bord de l'order block, stop derrière lui."""
        a = _atr(barres[:i + 1], PERIODE_ATR)
        if a is None:
            return None
        bas_ob, haut_ob = det["order_block"]
        if det["sens"] == "long":
            entree, stop = float(haut_ob), float(bas_ob) - 0.5 * a
            cible = entree + self.rr_min * (entree - stop)
        else:
            entree, stop = float(bas_ob), float(haut_ob) + 0.5 * a
            cible = entree - self.rr_min * (stop - entree)
        return self._verifier(symbole, "OTE", det["sens"], entree, stop, cible,
                              {"zone_ote": det["zone_ote"], "atr": round(a, 6)})

    def _verifier(self, symbole, scenario, sens, entree, stop, cible, motifs
                  ) -> Proposition | None:
        """Aucune proposition avec un stop nul, inversé ou un RR sous la cible.

        Un stop du mauvais côté du prix produit une taille de position ABSURDE plutôt
        qu'une erreur visible — c'est la division silencieuse qui ruine un compte.
        """
        distance = abs(entree - stop)
        if distance <= 0 or entree <= 0:
            return None
        bon_cote = (stop < entree) if sens == "long" else (stop > entree)
        if not bon_cote:
            return None
        rr = abs(cible - entree) / distance
        if rr < self.rr_min - 1e-9:
            return None
        return Proposition(symbole, scenario, sens, entree, stop, cible, rr, motifs)

    def raffiner_entree(self, proposition: dict, barres_intraday: list | None) -> dict:
        """Jambe 1H : attendre un CHoCH dans le sens du retournement avant d'engager.

        SANS DONNÉE INTRADAY, LA RÉPONSE EST « INDÉCIDABLE », JAMAIS « PRÊT ». Renvoyer
        un feu vert par défaut ferait silencieusement disparaître un filtre de la spec :
        le système se comporterait comme s'il avait vérifié quelque chose. La base de ce
        dépôt étant quotidienne, c'est le cas nominal aujourd'hui — d'où le refus.
        """
        if not barres_intraday or len(barres_intraday) < 4 * self.pivot:
            return {"statut": STATUT, "pret": False, "indecidable": True,
                    "motif": "aucune barre intraday — jambe 1H NON MESURABLE ici "
                             "(base quotidienne). Le filtre n'est pas 'passé', "
                             "il n'a pas pu être évalué."}
        j = len(barres_intraday) - 1
        c = choch(barres_intraday, j, pivot=self.pivot)
        attendu = "haussier" if proposition.get("sens") == "long" else "baissier"
        ok = bool(c.get("choch")) and c.get("sens") == attendu
        return {"statut": STATUT, "pret": ok, "indecidable": False, "choch": c,
                "motif": "" if ok else f"pas de CHoCH {attendu} sur l'unité de "
                                       "raffinement"}


class RiskManager:
    """Dimensionnement 1R, descente géométrique en drawdown, régime et corrélation.

    L'ORDRE DES TROIS FILTRES EST FIXE ET SIGNIFIANT : corrélation (quelles lignes),
    puis régime (quelle taille globale), puis DDM (quelle taille par trade). Chacun agit
    sur un objet différent ; les permuter donnerait le même portefeuille avec un
    dimensionnement différent, sans qu'on sache lequel a mordu.

    La machine DDM est un ÉTAT, pas un calcul : elle se souvient des trades précédents.
    Elle appartient donc à l'instance : deux portefeuilles n'en partagent jamais une.
    """

    def __init__(self, machine: MachineDDM | None = None) -> None:
        self.machine = machine or MachineDDM()

    def taille(self, equity: float, proposition: dict,
               facteur_regime: float = 1.0) -> dict:
        """Quantité = (capital × R courant × facteur régime) / distance au stop.

        Le facteur de régime multiplie la TAILLE, jamais le risque nominal 1R : en
        bear, on engage moitié moins de capital sur le même invalidant, ce qui divise
        par deux la perte en cas de stop. Réduire R lui-même reviendrait à éloigner le
        stop pour garder la même taille — l'inverse de l'intention.
        """
        entree, stop = float(proposition["entree"]), float(proposition["stop"])
        brut = taille_position(equity, entree, stop, self.machine)
        qte = brut * max(0.0, min(1.0, float(facteur_regime)))
        risque = qte * abs(entree - stop)
        return {"statut": STATUT, "quantite": qte, "notionnel": qte * entree,
                "risque_devise": risque,
                "risque_pct": (risque / equity) if equity > 0 else 0.0,
                "niveau_ddm": self.machine.etat(), "facteur_regime": facteur_regime}

    def enregistrer_trade(self, pnl_en_r: float) -> dict:
        """Un trade CLÔTURÉ, en R. C'est ce qui fait descendre ou remonter le niveau."""
        self.machine.enregistrer(pnl_en_r)
        return self.machine.etat()

    def selectionner(self, closes_reference, candidats: list[str],
                     closes_par_symbole: dict[str, list[float]], **kw) -> dict:
        """Lignes retenues après plafond de corrélation, et facteur de régime."""
        return exposition_autorisee(closes_reference, candidats,
                                    closes_par_symbole, **kw)

    def plan(self, equity: float, propositions: list[dict], closes_reference,
             closes_par_symbole: dict[str, list[float]], **kw) -> dict:
        """Chaîne complète : filtre corrélation → facteur régime → taille par ligne.

        Les propositions REFUSÉES sont renvoyées avec leur motif, pas supprimées :
        un plan qui n'affiche que ce qu'il garde rend ses règles invérifiables.
        """
        ordre = [p["symbole"] for p in propositions]
        sel = self.selectionner(closes_reference, ordre, closes_par_symbole, **kw)
        gardes = set(sel["retenus"])
        lignes, refusees = [], []
        for p in propositions:
            if p["symbole"] in gardes:
                lignes.append({**p, "dimensionnement":
                               self.taille(equity, p, sel["facteur_long"])})
            else:
                refusees.append({**p, "motif": "coupé par le plafond de corrélation"})
        return {"statut": STATUT, "facteur_long": sel["facteur_long"],
                "regime": sel["regime"].get("regime"), "lignes": lignes,
                "refusees": refusees, "correlation": sel["correlation"]}


__all__ = ["MarketStructureEngine", "Proposition", "RiskManager", "regime_marche"]
