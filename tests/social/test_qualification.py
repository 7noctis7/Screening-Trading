"""Une seconde voie d'intelligence X est un contournement, même involontaire.

AGENTS.md §9 : « Point d'entrée unique : `packages.intelligence.pipeline.qualifier()` ·
règles encodées, à ne pas contourner ». L'onglet livré sans ce passage affichait des
propos sans plafond d'authenticité, sans déduplication d'origine et sans exigence de
corroboration — exactement ce que la règle ferme. Le mécanisme par lequel un pipeline
devient dangereux est toujours le même : une opinion entre, traverse quelques couches,
et ressort en donnée.

Ce que ces tests épinglent :
  1. AUCUNE publication ne sort de la route sans son verdict ;
  2. `verifie` vaut toujours False — aucun des 66 comptes n'est authentifié ;
  3. un niveau de watchlist ASSORTI D'UNE RÉSERVE ne crédite pas le compte ;
  4. l'impact suit le caractère actionnable : le contrôle DURCIT l'exigence, jamais
     l'inverse ;
  5. une prédiction ne devient jamais un fait, quelle que soit la source.
"""
from __future__ import annotations

from datetime import UTC, datetime

from packages.intelligence.classify import Nature
from packages.intelligence.watchlist import WATCHLIST
from packages.social.modele import Classification as C
from packages.social.modele import Publication
from packages.social.qualification import _impact, _source, information, verdict

J = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)


def _pub(compte="eliz883", classification=C.TRADE_SIGNAL, texte="BTCUSDT long",
         ident="1"):
    return Publication(id=ident, compte=compte, ts=J, texte=texte,
                       classification=classification, ticker="BTC")


# ---- 1. rien ne sort sans verdict -------------------------------------------------

def test_AUCUNE_publication_ne_sort_de_la_route_sans_verdict(tmp_path):
    from apps.api.social_x import construire_filtre, publications
    from packages.social.store import StorePublications

    chemin = str(tmp_path / "x.db")
    s = StorePublications(chemin)
    s.ecrire([_pub(), _pub(ident="2", compte="inconnu42", classification=C.NEWS)])
    s.close()

    r = publications(construire_filtre(), db=chemin)
    assert r["n"] == 2
    for p in r["publications"]:
        assert "verdict" in p, "une publication sans verdict rouvre la seconde voie"
        assert set(p["verdict"]) >= {"statut", "exploitable", "confiance",
                                     "niveau_source"}


def test_le_verdict_est_calcule_dans_la_fonction_par_laquelle_TOUT_sort():
    """Le placer chez l'appelant le rendrait oubliable au prochain point d'entrée."""
    from pathlib import Path
    code = Path("apps/api/social_x.py").read_text()
    corps = code[code.index("def _serialiser"):code.index("def publications")]
    assert "verdict(p)" in corps


# ---- 2. et 3. la source n'est jamais créditée à crédit ----------------------------

def test_verifie_vaut_TOUJOURS_False():
    """AGENTS.md : aucun des 66 comptes n'est authentifié — ne pas le prétendre."""
    for compte in ("eliz883", "elonmusk", "inconnu42", "trendspider"):
        assert _source(compte).verifie is False


def test_un_niveau_ASSORTI_D_UNE_RESERVE_ne_credite_pas_le_compte():
    """`Candidat` dit « hypothèse, à valider avant tout usage ». Une note n'est pas
    une validation : les comptes dont `a_resoudre` est non vide restent en E."""
    avec_reserve = [c for c in WATCHLIST if c.a_resoudre]
    assert avec_reserve, "le test suppose qu'il en existe"
    for c in avec_reserve[:5]:
        assert str(_source(c.handle).niveau) == "E", c.handle


def test_un_niveau_SANS_reserve_est_bien_repris():
    sans = [c for c in WATCHLIST if not c.a_resoudre]
    assert str(_source(sans[0].handle).niveau) == str(sans[0].niveau_attendu)


def test_un_compte_INCONNU_tombe_au_niveau_le_plus_faible():
    assert str(_source("jamais_vu_99").niveau) == "E"


# ---- 4. l'impact durcit, il n'adoucit pas ----------------------------------------

def test_un_message_ACTIONNABLE_exige_PLUS_de_preuve():
    """L'exigence de corroboration croît avec l'impact : un signal d'entrée est ce sur
    quoi quelqu'un peut agir, donc ce qui doit être le plus exigeant."""
    for actionnable in (C.TRADE_SIGNAL, C.CLOSE_POSITION, C.MOVE_STOP,
                        C.TAKE_PROFIT_UPDATE, C.CANCEL_SIGNAL):
        assert _impact(actionnable) == "fort", actionnable
    assert _impact(C.EDUCATIONAL) == "faible"
    assert _impact(C.UNKNOWN) == "faible"


# ---- 5. une opinion ne devient pas un fait ---------------------------------------

def test_un_signal_est_une_PREDICTION_pas_une_affirmation_de_fait():
    assert information(_pub(classification=C.TRADE_SIGNAL)).nature is Nature.PREDICTION


def test_seule_une_NEWS_pretend_rapporter_un_fait():
    assert information(_pub(classification=C.NEWS)).nature is Nature.FACTUELLE
    assert information(_pub(classification=C.EDUCATIONAL)).nature is Nature.OPINION


def test_meme_une_source_de_haut_niveau_ne_rend_pas_un_signal_EXPLOITABLE():
    """Le plafond tient : aucun compte n'étant authentifié, rien n'atteint FACT."""
    v = verdict(_pub(compte="elonmusk", classification=C.TRADE_SIGNAL))
    assert v["exploitable"] is False
    assert v["statut"] != "FACT"
