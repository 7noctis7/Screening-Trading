"""Un lot OUVERT en double se retire — et on retire la COPIE, jamais l'original.

D'OÙ VIENT CET OUTIL (18/09). `diag-journal` détectait ces doublons depuis le 03/09 et
se contentait de les imprimer. Aucun script de la chaîne ne les retirait :
`annuler_doublons_correction` ne traite que les doublons de FERMETURE. Résultat, le
doublon « QQQ ×2, 3,586126 @ 716,86 le 17/09 » a survécu à trois passages de
`make reparer-journal`. Un défaut détecté sans remède est un défaut qui reste.

POURQUOI IL FAUT LE RETIRER : un lot ouvert en double fournit un lot de PLUS à apparier
en FIFO. La prochaine vente réelle fermera les deux, et le second produira du
« réalisé » sans contrepartie chez le courtier — l'invention même que cette chaîne
existe pour combattre.
"""

from __future__ import annotations

from datetime import UTC, datetime

from packages.research.doublons_ouverts import identifiants_retires, plan


class _Lot:
    def __init__(self, ident, qty=3.586126, prix=716.86, jour="2026-09-17",
                 features=None, ferme=False, symbole="QQQ"):
        self.id, self.instrument = ident, symbole
        self.qty, self.entry_price = qty, prix
        self.entry_ts = datetime.fromisoformat(f"{jour}T19:08:00+00:00")
        self.exit_ts = datetime.now(UTC) if ferme else None
        self.features_snapshot = features or {}


def test_le_cas_REEL_du_17_09_garde_la_DECISION():
    """`P-` porte les features de décision ; `C-` est le même ordre reconstitué après
    coup depuis le fill. Garder la reconstitution perdrait la capture ML pour rien."""
    d = plan([_Lot("C-QQQ-4a1b2c3d"), _Lot("P-20260917-Alpaca-QQQ",
                                           features={"decision_price": 716.0})])
    assert len(d) == 1
    assert d[0].garde == "P-20260917-Alpaca-QQQ"
    assert d[0].retires == ("C-QQQ-4a1b2c3d",)
    assert identifiants_retires(d) == ["C-QQQ-4a1b2c3d"]


def test_l_import_historique_cede_toujours_le_pas():
    """`LEG-` a une provenance illisible : entre lui et un ordre du robot, il n'y a pas
    à hésiter."""
    d = plan([_Lot("LEG-ad4ac9fa7f59"), _Lot("C-QQQ-4a1b2c3d")])
    assert d[0].garde == "C-QQQ-4a1b2c3d"


def test_les_lots_FERMES_ne_sont_JAMAIS_touches():
    """Retirer un lot fermé effacerait un réalisé déjà comptabilisé. C'est une autre
    décision, qui se prend avec les fills du courtier sous les yeux."""
    assert plan([_Lot("P-a", ferme=True), _Lot("C-b", ferme=True)]) == []
    # …et un fermé ne « doublonne » pas non plus un ouvert.
    assert plan([_Lot("P-a", ferme=True), _Lot("C-b")]) == []


def test_deux_achats_REELLEMENT_distincts_ne_sont_pas_groupes():
    """Quantité, prix ou jour différent ⇒ ce sont deux lots, pas une copie."""
    assert plan([_Lot("P-a"), _Lot("P-b", qty=1.0)]) == []
    assert plan([_Lot("P-a"), _Lot("P-b", prix=717.0)]) == []
    assert plan([_Lot("P-a"), _Lot("P-b", jour="2026-09-16")]) == []
    assert plan([_Lot("P-a"), _Lot("P-b", symbole="VZ")]) == []


def test_a_rang_EGAL_le_resultat_est_DETERMINISTE():
    """Deux exécutions doivent retirer la même ligne, sinon la réparation dépend de
    l'ordre de lecture de la base — et devient irrejugeable."""
    lots = [_Lot("P-zzz"), _Lot("P-aaa")]
    assert plan(lots)[0].garde == "P-aaa"
    assert plan(list(reversed(lots)))[0].garde == "P-aaa"


def test_les_FEATURES_departagent_avant_l_identifiant():
    """À provenance égale, celui qui sert la calibration ML a la préséance."""
    d = plan([_Lot("P-aaa"), _Lot("P-zzz", features={"decision_price": 1.0})])
    assert d[0].garde == "P-zzz"


def test_un_TRIPLET_ne_garde_qu_UN_exemplaire():
    d = plan([_Lot("C-b"), _Lot("P-a"), _Lot("LEG-c")])
    assert d[0].garde == "P-a"
    assert set(d[0].retires) == {"C-b", "LEG-c"}


def test_l_archive_porte_de_quoi_REJUGER_le_retrait():
    """Un retrait sans sa preuve n'est pas rejugeable."""
    d = plan([_Lot("C-QQQ-4a1b2c3d"), _Lot("P-20260917-Alpaca-QQQ")])[0].en_dict()
    assert d["symbole"] == "QQQ" and d["jour"] == "2026-09-17"
    assert d["qty"] == 3.586126 and d["prix"] == 716.86
    assert d["garde"] and d["retires"]
