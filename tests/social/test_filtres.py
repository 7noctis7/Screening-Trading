"""Une page qui n'affiche rien est indiscernable d'un flux en panne.

C'est le risque central d'une interface de filtres, et il ne vient pas d'un bug : il
vient d'un DÉFAUT mal choisi. Une sélection vide lue comme « ne garder aucun compte »
donne une page blanche au premier chargement, sans message d'erreur, sans rien à
signaler. L'utilisateur conclut que le flux est mort.

Ce que ces tests épinglent :
  1. une sélection vide veut dire TOUS, jamais aucun ;
  2. la recherche ignore la casse ET les accents (contenu bilingue) ;
  3. la recherche est partielle (« bit » retrouve « Bitcoin ») ;
  4. elle porte aussi sur le ticker, le symbole, la classification et les niveaux ;
  5. les critères se combinent en ET, et se cumulent en OU à l'intérieur d'un critère ;
  6. une publication SANS direction n'est ni LONG ni SHORT — filtrer sur LONG l'exclut.
"""
from __future__ import annotations

from datetime import UTC, datetime

from packages.social.filtres import Filtre, appliquer, contient, normaliser
from packages.social.modele import Classification, Direction, Publication

C = Classification
J = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)


def _pub(ident, compte, texte, **kw) -> Publication:
    kw.setdefault("classification", C.UNKNOWN)
    return Publication(id=ident, compte=compte, ts=kw.pop("ts", J), texte=texte, **kw)


LOT = [
    _pub("1", "astekz", "BTC breakout au-dessus de la résistance, TP1 en vue",
         classification=C.TRADE_SIGNAL, ticker="BTC", symbole="BTCUSDT",
         direction=Direction.LONG, extraits={"tp1": 65000.0, "sl": 61000.0}),
    _pub("2", "micro2macr0", "Je passe SHORT sur Ethereum, support cassé",
         classification=C.TRADE_SIGNAL, ticker="ETH", symbole="ETHUSDT",
         direction=Direction.SHORT, extraits={"entree": 2400.0}),
    _pub("3", "trendspider", "Petit rappel sur la lecture des volumes",
         classification=C.EDUCATIONAL),
    _pub("4", "eliz883", "SOL tient son support, j'observe",
         classification=C.MARKET_ANALYSIS, ticker="SOL", symbole="SOLUSDT"),
    _pub("5", "astekz", "Je remonte mon stop sur Bitcoin",
         classification=C.MOVE_STOP, ticker="BTC", symbole="BTCUSDT",
         direction=Direction.LONG),
]


def _ids(pubs) -> set[str]:
    return {p.id for p in pubs}


# ---- 1. le défaut ----------------------------------------------------------------

def test_un_filtre_VIDE_rend_TOUT_et_non_rien():
    """LE défaut qui décide de la première impression. Vide = tous, jamais aucun."""
    assert _ids(appliquer(LOT, Filtre())) == {"1", "2", "3", "4", "5"}
    assert not Filtre().actif()


def test_le_tri_va_du_plus_recent_au_plus_ancien():
    vieux = _pub("0", "astekz", "hier", ts=datetime(2026, 9, 23, tzinfo=UTC))
    assert appliquer([vieux, *LOT], Filtre())[-1].id == "0"


# ---- 2. et 3. la recherche -------------------------------------------------------

def test_la_recherche_ignore_la_CASSE():
    for graphie in ("btc", "BTC", "Btc"):
        assert _ids(appliquer(LOT, Filtre(requete=graphie))) == {"1", "5"}, graphie


def test_la_recherche_ignore_les_ACCENTS():
    """Contenu bilingue : « resistance » au clavier trouve « résistance » écrit."""
    assert _ids(appliquer(LOT, Filtre(requete="resistance"))) == {"1"}
    assert _ids(appliquer(LOT, Filtre(requete="résistance"))) == {"1"}


def test_la_recherche_est_PARTIELLE():
    """« bit » retrouve « Bitcoin » — sinon il faut connaître le mot exact."""
    assert _ids(appliquer(LOT, Filtre(requete="bit"))) == {"5"}


def test_plusieurs_mots_se_combinent_en_ET_pas_en_phrase():
    assert _ids(appliquer(LOT, Filtre(requete="btc breakout"))) == {"1"}
    assert _ids(appliquer(LOT, Filtre(requete="breakout btc"))) == {"1"}


# ---- 4. l'étendue de la recherche ------------------------------------------------

def test_la_recherche_porte_sur_le_SYMBOLE_pas_seulement_le_texte():
    """Aucun message n'écrit « BTCUSDT » en toutes lettres — la paire est un champ."""
    assert _ids(appliquer(LOT, Filtre(requete="BTCUSDT"))) == {"1", "5"}


def test_la_recherche_porte_sur_la_CLASSIFICATION():
    assert _ids(appliquer(LOT, Filtre(requete="move_stop"))) == {"5"}


def test_la_recherche_porte_sur_la_DIRECTION():
    assert _ids(appliquer(LOT, Filtre(requete="short"))) == {"2"}


def test_la_recherche_retrouve_un_NIVEAU_extrait():
    """« 65000 » retrouve le message dont le TP1 vaut 65000.0, pas seulement 65000.0."""
    assert _ids(appliquer(LOT, Filtre(requete="65000"))) == {"1"}
    assert _ids(appliquer(LOT, Filtre(requete="TP1"))) == {"1"}


def test_un_champ_ABSENT_n_est_pas_une_chaine_vide_qui_matcherait_tout():
    muet = _pub("x", "astekz", "rien de particulier")
    assert contient(muet, "") is True
    assert contient(muet, "BTC") is False


# ---- 5. la combinaison -----------------------------------------------------------

def test_compte_ET_mot_cle():
    """L'exemple de la demande : @astekz + BTC."""
    r = appliquer(LOT, Filtre(comptes=["astekz"], requete="BTC"))
    assert _ids(r) == {"1", "5"}


def test_deux_comptes_ET_un_mot_cle():
    """astekz + micro2macr0, mot-clé SHORT → seul le message short de micro2macr0."""
    r = appliquer(LOT, Filtre(comptes=["astekz", "micro2macr0"], requete="SHORT"))
    assert _ids(r) == {"2"}


def test_le_compte_est_insensible_a_la_casse():
    assert _ids(appliquer(LOT, Filtre(comptes=["Micro2Macr0"]))) == {"2"}


def test_classification_et_direction_se_combinent():
    r = appliquer(LOT, Filtre(classifications=[C.TRADE_SIGNAL],
                              directions=[Direction.LONG]))
    assert _ids(r) == {"1"}


def test_filtrer_par_symbole():
    assert _ids(appliquer(LOT, Filtre(symboles=["ETHUSDT"]))) == {"2"}


# ---- 6. l'absence n'est pas une valeur -------------------------------------------

def test_une_publication_SANS_direction_n_est_NI_long_NI_short():
    """Elle n'est pas « neutre » : elle n'a pas de contenu directionnel du tout."""
    sans = [p for p in LOT if p.direction is None]
    assert {p.id for p in sans} == {"3", "4"}
    for d in (Direction.LONG, Direction.SHORT):
        assert _ids(appliquer(LOT, Filtre(directions=[d]))).isdisjoint({"3", "4"})


def test_normaliser_ne_casse_pas_les_chiffres_ni_la_ponctuation():
    assert normaliser("TP1 : 65 000 $") == "tp1 : 65 000 $"
