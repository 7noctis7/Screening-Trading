"""D'où vient l'écart quand le COURTIER détient ce que le journal ignore ?

Constat du 05/09, après les deux scripts de réparation : le courtier détient 335,50
AVAX, le journal 3,65 ; 219,80 LINK contre 82,41 ; 85,27 OSCR contre 0. Les lots
orphelins (journal > courtier) sont un trou de SORTIES, déjà outillé. Celui-ci va dans
l'AUTRE sens, et `completer_ouvertures` ne l'a pas refermé alors qu'il venait de
tourner.

`diag_journal_compte` CONSTATE cet écart. Ce module dit de quoi il est fait, par une
identité exacte plutôt que par une hypothèse :

    manque_ouvert  =  achats_non_journalises  +  sur_fermeture

    manque_ouvert          = (acheté − vendu) − ouvert(journal)   le surplus du courtier
    achats_non_journalises = acheté − total(journal)              entrées jamais écrites
    sur_fermeture          = fermé(journal) − vendu               sorties INVENTÉES

La démonstration tient en une ligne : (acheté − fermé − ouvert) + (fermé − vendu)
= acheté − vendu − ouvert. Les deux termes s'additionnent donc EXACTEMENT au manque, ce
qui interdit d'attribuer l'écart à la mauvaise cause — et rend la mesure réfutable : si
l'identité ne se referme pas, c'est ce module qui a tort, pas la donnée.

Les deux causes n'ont ni le même remède ni la même gravité. Un achat non journalisé est
un TROU : le compte porte une position dont le journal n'a pas le prix de revient. Une
sur-fermeture est une INVENTION : le journal a soldé des unités que le courtier n'a
jamais vendues, donc il a produit du « réalisé » sans contrepartie. La seconde
contamine les statistiques ; la première les rend seulement incomplètes.

DEUX CHEMINS DE FERMETURE, qui ne se vérifient pas de la même façon :
  - `reconciliation-journal:<uuid>` NOMME l'ordre réel → comparaison exacte, ordre par
    ordre. C'est le seul niveau où une sur-fermeture est imputable à un fill précis.
  - `reconciliation paper (reduce/close)` ne nomme rien → comparaison par symbole
    seulement.
On publie les deux séparément : mélangés, un excédent imputable se noierait dans un
agrégat, et c'est précisément l'imputation qui permet de corriger.

PIÈGE DÉJÀ PAYÉ (LINK, 04/09). Un ordre de vente ferme LÉGITIMEMENT plusieurs lots à la
suite : `_plan` regroupe les chaînes `P-` et `C-` dans un seul pool FIFO par symbole.
Voir deux lots fermés par la même vente n'est donc PAS un doublon — j'ai posé un P0 sur
cette base sans faire l'addition, et l'addition disait « exact ». Un excédent n'existe
que si la somme des quantités fermées DÉPASSE la quantité réellement vendue.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Aucune contrainte de LONGUEUR sur l'identifiant : un minimum arbitraire écarterait en
# silence un motif réel plus court, et le silence est le seul mode de défaillance qu'on
# ne peut pas mesurer. L'appariement aux ordres réels (`oid not in reels`) filtre déjà
# tout ce qui ne désigne pas un fill du compte.
_UUID = re.compile(r"reconciliation-journal:([0-9a-fA-F-]+)")

# Tolérance RELATIVE : les quantités crypto portent 9 décimales, et une comparaison
# stricte ferait « dépasser » 273,125383999 face à 273,12538382. Cf. la règle du dépôt
# sur les seuils flottants — jamais de comparaison nue sur des flottants accumulés.
def _depasse(somme: float, reference: float) -> bool:
    return somme - reference > 1e-6 * max(1.0, abs(reference))


def _canon(sym: str) -> str:
    from packages.research.biais_fermeture import symbole_canonique
    return symbole_canonique(sym or "")


def ordre_reference(motif: str | None) -> str | None:
    """Identifiant de l'ordre RÉEL cité par un motif de sortie, ou None."""
    m = _UUID.search(motif or "")
    return m.group(1) if m else None


@dataclass
class EcartOrdre:
    """Un ordre de vente réel, et ce que le journal a fermé en s'y référant."""
    ordre: str
    symbole: str
    vendu_reel: float
    ferme_journal: float
    lots: list[str] = field(default_factory=list)

    @property
    def exces(self) -> float:
        return self.ferme_journal - self.vendu_reel

    @property
    def surferme(self) -> bool:
        return _depasse(self.ferme_journal, self.vendu_reel)


@dataclass
class EcartSymbole:
    """Décomposition du manque, pour UN symbole. Les deux causes s'additionnent."""
    symbole: str
    achete: float
    vendu: float
    ferme_journal: float
    ouvert_journal: float

    @property
    def detenu_attendu(self) -> float:
        return self.achete - self.vendu

    @property
    def manque_ouvert(self) -> float:
        """> 0 : le courtier porte plus que le journal n'en connaît d'ouvert."""
        return self.detenu_attendu - self.ouvert_journal

    @property
    def achats_non_journalises(self) -> float:
        return self.achete - (self.ferme_journal + self.ouvert_journal)

    @property
    def sur_fermeture(self) -> float:
        """> 0 : le journal a soldé des unités que le courtier n'a pas vendues."""
        return self.ferme_journal - self.vendu

    def identite_verifiee(self) -> bool:
        """L'identité DOIT se refermer — sinon la décomposition est fausse."""
        somme = self.achats_non_journalises + self.sur_fermeture
        manque = self.manque_ouvert
        return abs(somme - manque) <= 1e-6 * max(1.0, abs(manque))


def par_ordre(trades: list, ordres: list[dict]) -> list[EcartOrdre]:
    """Ordre réel par ordre réel : le journal a-t-il fermé plus que le fill ne portait ?

    Seules les sorties qui CITENT un ordre sont concernées — les autres ne sont
    imputables à aucun fill, et les imputer d'office fabriquerait l'excédent cherché."""
    reels = {str(o.get("id", "")): o for o in ordres
             if str(o.get("side", "")).lower() == "sell"}
    par_id: dict[str, EcartOrdre] = {}
    for t in trades:
        oid = ordre_reference(getattr(t, "exit_reason", None))
        if oid is None or oid not in reels:
            continue
        o = reels[oid]
        e = par_id.setdefault(oid, EcartOrdre(
            ordre=oid, symbole=_canon(o.get("symbol", "")),
            vendu_reel=float(o.get("qty", 0) or 0), ferme_journal=0.0))
        e.ferme_journal += float(getattr(t, "qty", 0) or 0)
        e.lots.append(str(getattr(t, "id", "")))
    return sorted(par_id.values(), key=lambda e: -e.exces)


def par_symbole(trades: list, ordres: list[dict]) -> list[EcartSymbole]:
    """Décomposition du manque par symbole canonique (achats + ventes du courtier)."""
    achats: dict[str, float] = {}
    ventes: dict[str, float] = {}
    for o in ordres:
        cible = ventes if str(o.get("side", "")).lower() == "sell" else achats
        s = _canon(o.get("symbol", ""))
        cible[s] = cible.get(s, 0.0) + float(o.get("qty", 0) or 0)
    fermes: dict[str, float] = {}
    ouverts: dict[str, float] = {}
    for t in trades:
        s = _canon(getattr(t, "instrument", ""))
        cible = fermes if getattr(t, "exit_ts", None) is not None else ouverts
        cible[s] = cible.get(s, 0.0) + float(getattr(t, "qty", 0) or 0)
    out = [EcartSymbole(symbole=s, achete=achats.get(s, 0.0),
                        vendu=ventes.get(s, 0.0), ferme_journal=fermes.get(s, 0.0),
                        ouvert_journal=ouverts.get(s, 0.0))
           for s in sorted(set(achats) | set(ventes) | set(fermes) | set(ouverts))]
    return sorted(out, key=lambda e: -abs(e.manque_ouvert))
