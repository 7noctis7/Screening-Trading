"""Watchlist X — une liste de comptes À VÉRIFIER, pas une liste de comptes fiables.

C'est la distinction la plus importante de ce module. La liste ci-dessous est un point de
départ fourni par l'utilisateur du projet. Aucun de ces comptes n'a été authentifié par le
système, aucun nombre d'abonnés n'a été relevé, aucune exactitude passée n'a été mesurée.

Ils partent donc TOUS avec `verifie=False` et `abonnes=None`, ce qui les plafonne
automatiquement à 0,60 de crédit (cf. `sources.PLAFOND_NON_VERIFIE`) et les empêche d'être
utilisables seuls sur une information à impact. Le niveau indiqué est un niveau ATTENDU —
une hypothèse à confirmer — et non un niveau acquis.

Inventer un statut de vérification ou un nombre d'abonnés produirait exactement le défaut que
tout ce paquet existe pour empêcher : une donnée fabriquée présentée comme un fait.

NUANCE « SOURCE PRIMAIRE ». Être primaire est CONTEXTUEL, pas une propriété du compte. Le
dirigeant d'une entreprise est source primaire sur SON entreprise et source d'opinion sur la
macro. `primaire_sur` porte cette nuance ; hors de ce périmètre, le compte retombe au niveau B.
"""

from __future__ import annotations

from dataclasses import dataclass

from packages.intelligence.sources import Niveau, Source

MACRO, ACTIONS, CRYPTO, TECH, VC = "macro", "actions", "crypto", "tech", "venture"


@dataclass(frozen=True)
class Candidat:
    """Hypothèse sur un compte, à valider avant tout usage."""
    handle: str
    niveau_attendu: Niveau
    domaines: tuple[str, ...]
    primaire_sur: tuple[str, ...] = ()      # entités sur lesquelles le compte est source primaire
    a_resoudre: str = ""                    # ce qui empêche de l'utiliser tel quel


def _c(h, n, d, p=(), r=""):
    return Candidat(h, n, d, p, r)


# Dirigeants et institutions : source PRIMAIRE sur leur propre périmètre, experts ailleurs.
_DIRIGEANTS = [
    _c("realDonaldTrump", Niveau.B_EXPERT, (MACRO, "geopolitique"), ("politique US",)),
    _c("elonmusk", Niveau.B_EXPERT, (TECH, ACTIONS, CRYPTO), ("Tesla", "SpaceX", "xAI")),
    _c("LisaSu", Niveau.B_EXPERT, (TECH, ACTIONS), ("AMD",)),
    _c("brian_armstrong", Niveau.B_EXPERT, (CRYPTO,), ("Coinbase",)),
    _c("cz_binance", Niveau.B_EXPERT, (CRYPTO,), ("Binance",)),
    _c("saylor", Niveau.B_EXPERT, (CRYPTO,), ("MicroStrategy",)),
    _c("VitalikButerin", Niveau.B_EXPERT, (CRYPTO,), ("Ethereum",)),
    _c("vladtenev", Niveau.B_EXPERT, (ACTIONS,), ("Robinhood",)),
    _c("CathieDWood", Niveau.B_EXPERT, (ACTIONS, TECH), ("ARK Invest",)),
    _c("ARKInvest", Niveau.B_EXPERT, (ACTIONS, TECH), ("ARK Invest",)),
    _c("alexandr_wang", Niveau.B_EXPERT, (TECH,), ("Scale AI",)),
    _c("garrytan", Niveau.B_EXPERT, (VC, TECH), ("Y Combinator",)),
    _c("pmarca", Niveau.B_EXPERT, (VC, TECH), ("a16z",)),
    _c("a16z", Niveau.B_EXPERT, (VC, TECH), ("a16z",)),
    _c("a16zcrypto", Niveau.B_EXPERT, (VC, CRYPTO), ("a16z crypto",)),
    _c("foundersfund", Niveau.B_EXPERT, (VC,), ("Founders Fund",)),
    _c("ylecun", Niveau.B_EXPERT, (TECH,), ("Meta AI",)),
    _c("JoeChalom", Niveau.B_EXPERT, (CRYPTO, ACTIONS)),
    _c("Jensen Huang", Niveau.B_EXPERT, (TECH, ACTIONS), ("NVIDIA",),
       "NOM, pas un handle X — le handle réel doit être résolu et authentifié avant usage"),
]

# Analystes, économistes, chercheurs : niveau B attendu DANS leur domaine.
_ANALYSTES = [
    _c("AswathDamodaran", Niveau.B_EXPERT, (ACTIONS, "valorisation")),
    _c("fundstrat", Niveau.B_EXPERT, (ACTIONS, MACRO)),
    _c("FundstratCap", Niveau.B_EXPERT, (ACTIONS, MACRO)),
    _c("KobeissiLetter", Niveau.B_EXPERT, (MACRO, ACTIONS)),
    _c("unusual_whales", Niveau.B_EXPERT, (ACTIONS, "flux")),
    _c("NCheron_bourse", Niveau.B_EXPERT, (ACTIONS, MACRO)),
    _c("BrianFeroldi", Niveau.B_EXPERT, (ACTIONS,)),
    _c("Brian_Stoffel_", Niveau.B_EXPERT, (ACTIONS,)),
    _c("lexfridman", Niveau.B_EXPERT, (TECH,)),
    _c("CBinsights", Niveau.B_EXPERT, (VC, TECH)),
    _c("whale_alert", Niveau.B_EXPERT, (CRYPTO, "on-chain")),
    _c("massifund", Niveau.C_SUIVI, (ACTIONS, MACRO)),
    _c("TrendSpider", Niveau.C_SUIVI, (ACTIONS, "technique")),
    _c("VisualCap", Niveau.C_SUIVI, (MACRO, ACTIONS)),
    _c("EconomyApp", Niveau.C_SUIVI, (MACRO,)),
    _c("WatcherGuru", Niveau.C_SUIVI, (CRYPTO,)),
]

# Comptes très suivis dont l'expertise reste à établir : niveau C par défaut. Le nombre
# d'abonnés ne les fait PAS monter — il ne vaut que 0,08 au maximum dans le score.
_A_ETABLIR = [
    "AboutRWAs", "AshCrypto", "felixprehn", "thestochwhale", "ethereumJoseph",
    "MrMikeInvesting", "IncomeSharks", "alc2002", "chad_ventures", "GaryVec",
    "Freedom_By_40", "smatthewschultz", "CyclesWithBach", "StockSavyShay", "Micro2Macr0",
    "AltcoinGem", "Quatr_App", "MikeLongTerm", "eliz883", "CryptoGodJohn", "KrisPatel99",
    "arny_trezzi", "TickerSymbolYOU", "amitisinvesting", "FromValue", "ArkkDaily",
    "DominicRinaldi9", "iamtomnash", "PowerHasheur", "LuoshendPeng", "yassine_elman",
]

WATCHLIST: tuple[Candidat, ...] = tuple(
    _DIRIGEANTS + _ANALYSTES
    + [_c(h, Niveau.C_SUIVI, (), (), "domaine d'expertise et authenticité à établir")
       for h in _A_ETABLIR]
)


def en_source(c: Candidat, sujet_entite: str = "") -> Source:
    """Convertit un candidat en `Source` UTILISABLE — c'est-à-dire non vérifiée.

    `sujet_entite` : si l'information porte sur une entité dont le compte est source primaire
    (« Tesla » pour le dirigeant de Tesla), le niveau monte à A. Hors de ce périmètre, il reste
    au niveau attendu — un dirigeant qui commente la macro n'est pas une source primaire macro.
    """
    niveau = c.niveau_attendu
    if sujet_entite and any(e.lower() in sujet_entite.lower() for e in c.primaire_sur):
        niveau = Niveau.A_PRIMAIRE
    return Source(handle=c.handle, niveau=niveau, verifie=False, abonnes=None,
                  domaines=c.domaines,
                  note=c.a_resoudre or "compte de watchlist — authentification requise")


def a_verifier() -> list[Candidat]:
    """Comptes qui ne peuvent PAS être utilisés tels quels. Aujourd'hui : tous.

    Cette fonction est faite pour rester bruyante. Le jour où elle renvoie une liste vide,
    c'est que quelqu'un a réellement authentifié chaque compte."""
    return list(WATCHLIST)


def resume() -> dict:
    from collections import Counter
    n = Counter(c.niveau_attendu.value for c in WATCHLIST)
    # Deux problèmes distincts, à ne pas confondre : un HANDLE qu'on ne sait pas résoudre, et
    # un domaine d'expertise qu'on n'a pas établi. Le premier empêche même de trouver le compte.
    return {"total": len(WATCHLIST), "par_niveau_attendu": dict(sorted(n.items())),
            "authentifies": 0,
            "handles_a_resoudre": [c.handle for c in WATCHLIST if "handle" in c.a_resoudre],
            "expertise_a_etablir": sum(1 for c in WATCHLIST
                                       if c.a_resoudre and "handle" not in c.a_resoudre),
            "avertissement": ("niveaux ATTENDUS, non acquis — aucun compte n'est authentifié, "
                              "tous sont plafonnés à 0,60 de crédit et aucun n'est utilisable "
                              "seul sur une information à impact")}
