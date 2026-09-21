"""« DONNÉE INDISPONIBLE » doit dire LAQUELLE des trois causes, pas juste qu'il manque.

CE QUE L'UTILISATEUR A VU (21/09). Les cinq fenêtres de performance du rideau affichaient
« DONNÉE INDISPONIBLE ». Le motif disait « /api/intro n'a rien renvoyé » — exact, et
inutilisable : il ne dit pas s'il faut attendre, relancer l'API, ou aller chercher un trou
dans les données.

La cause réelle était la plus banale : `/api/intro` est servi par le snapshot COMPLET, que
l'API reconstruit pendant une à trois minutes après un `make up`, alors que le rideau
n'attend les chiffres que 2,5 s. Rien n'était cassé — et rien ne le disait.

Trois causes, trois messages :
  · la requête court encore        → attente, le snapshot se reconstruit ;
  · la requête a échoué            → API injoignable ;
  · elle a répondu sans la période → motif du serveur, ou « absente du payload ».
"""

import pathlib

INTRO = pathlib.Path(__file__).resolve().parents[2] / "apps" / "web" / "components" / "intro"
BEATS = (INTRO / "IntroBeats.tsx").read_text(encoding="utf-8")
SEQ = (INTRO / "IntroSequence.tsx").read_text(encoding="utf-8")
CONF = (INTRO / "introConfig.ts").read_text(encoding="utf-8")


def test_les_deux_causes_sans_reponse_ont_chacune_leur_message():
    assert '"/api/intro n\'a pas encore répondu' in BEATS or \
           "n'a pas encore répondu" in BEATS
    assert "injoignable" in BEATS
    # Et elles ne disent PAS la même chose : un message unique reviendrait à l'ancien.
    debut = BEATS.split("const SANS_REPONSE", 1)[1].split("};", 1)[0]
    assert "attente:" in debut and "erreur:" in debut
    assert debut.count("/api/intro") == 2


def test_la_cause_attente_nomme_le_make_up_et_la_duree():
    """Sans le « 1 à 3 min », le message dit d'attendre sans dire combien — donc on
    conclut à une panne au bout de dix secondes."""
    assert "make up" in BEATS
    assert "1 à 3 min" in BEATS


def test_la_sequence_TRANSMET_l_etat_de_la_requete():
    """Le message le plus juste du monde ne sert à rien si le composant ne sait pas
    dans quel cas il est."""
    assert "isError" in SEQ
    assert 'etat={intro !== undefined ? undefined : introKo ? "erreur" : "attente"}' in SEQ


def test_une_periode_ABSENTE_du_payload_reste_distincte_d_une_absence_de_reponse():
    """L'API a répondu mais n'a pas cette fenêtre : ce n'est pas le même diagnostic,
    et ça ne doit pas produire le même texte."""
    assert "période absente du payload" in BEATS


def test_aucune_constante_ne_pretend_que_les_periodes_se_SAUTENT():
    """`SANS_DONNEES_SAUTE_PERIODES = true` a survécu à la décision INVERSE du 16/09 :
    les battements ne se sautent pas, ils s'affichent en disant pourquoi ils sont vides
    (sauter laissait cinq secondes de noir indiscernables d'une panne). Une constante
    exportée qui affirme le contraire du code est un piège pour le prochain lecteur."""
    assert "SANS_DONNEES_SAUTE_PERIODES" not in CONF
    assert "SANS_DONNEES_SAUTE_PERIODES" not in BEATS
