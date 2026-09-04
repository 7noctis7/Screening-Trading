"""Le journal ignore la moitié des achats : ce que la complétion a le droit d'écrire.

Ces tests verrouillent les trois choses qui rendraient l'outil dangereux :
un prix de revient pris sur les mauvais fills, une correction inventée là où le
courtier est muet, et une suppression déguisée en réparation.
"""

from __future__ import annotations

from packages.research.completion_ouvertures import (
    achats_par_symbole,
    ouvertures_manquantes,
    quantites_journalisees,
)


class _Rec:
    def __init__(self, instrument, qty):
        self.instrument, self.qty = instrument, qty


def _achat(sym, qty, price, date, broker="Alpaca"):
    return {"symbol": sym, "side": "buy", "qty": qty, "price": price,
            "date": date, "broker": broker}


def test_groupe_par_symbole_canonique_et_trie_par_date():
    ordres = [_achat("AVAXUSD", 5, 30.0, "2026-08-02T10:00:00Z"),
              _achat("AVAX/USDC", 3, 20.0, "2026-08-01T10:00:00Z")]
    par = achats_par_symbole(ordres)
    assert list(par) == ["AVAX"]
    assert [f["price"] for f in par["AVAX"]] == [20.0, 30.0]     # chronologique


def test_fill_sans_date_ou_sans_prix_est_ecarte():
    """On ne complète pas un registre avec des lignes qu'on ne sait pas dater."""
    ordres = [_achat("QQQ", 5, 500.0, ""),
              _achat("QQQ", 5, 0.0, "2026-08-01T10:00:00Z"),
              {"symbol": "QQQ", "side": "sell", "qty": 5, "price": 500.0,
               "date": "2026-08-01T10:00:00Z"}]
    assert achats_par_symbole(ordres) == {}


def test_lots_fermes_comptent_comme_journalises():
    """Un lot fermé a bien été ouvert : l'ignorer recréerait des lots déjà connus."""
    assert quantites_journalisees([_Rec("AVAX/USDC", 400), _Rec("AVAXUSD", 226)]) == {
        "AVAX": 626.0}


def test_prix_du_manquant_est_le_vwap_des_fills_NON_couverts():
    """Le cœur de l'outil : 100 unités connues, 100 manquantes → seuls les fills
    restants comptent. Le VWAP global (15 $) serait faux ; le bon est 20 $."""
    ordres = [_achat("PATH", 100, 10.0, "2026-08-01T10:00:00Z"),
              _achat("PATH", 100, 20.0, "2026-08-05T10:00:00Z")]
    a_creer, en_trop = ouvertures_manquantes(ordres, {"PATH": 100.0})
    assert en_trop == []
    assert len(a_creer) == 1
    lot = a_creer[0]
    assert lot["symbole"] == "PATH"
    assert lot["qty"] == 100.0
    assert abs(lot["prix"] - 20.0) < 1e-9
    assert lot["date"] == "2026-08-05T10:00:00Z"        # début RÉEL de l'exposition


def test_fill_coupe_en_deux_quand_le_journal_en_couvre_une_partie():
    """60 connues sur un premier fill de 100 : les 40 restantes gardent SON prix."""
    ordres = [_achat("SOL/USDC", 100, 10.0, "2026-08-01T10:00:00Z"),
              _achat("SOL/USDC", 100, 30.0, "2026-08-02T10:00:00Z")]
    a_creer, _ = ouvertures_manquantes(ordres, {"SOL": 60.0})
    lot = a_creer[0]
    assert abs(lot["qty"] - 140.0) < 1e-9
    assert abs(lot["prix"] - (40 * 10.0 + 100 * 30.0) / 140.0) < 1e-9


def test_symbole_deja_couvert_ne_produit_rien():
    ordres = [_achat("QQQ", 10, 500.0, "2026-08-01T10:00:00Z")]
    assert ouvertures_manquantes(ordres, {"QQQ": 10.0}) == ([], [])


def test_ecart_dans_la_tolerance_ne_produit_rien():
    """0,5 % d'écart = arrondi de fill, pas un achat perdu."""
    ordres = [_achat("QQQ", 1000, 500.0, "2026-08-01T10:00:00Z")]
    assert ouvertures_manquantes(ordres, {"QQQ": 995.0}) == ([], [])


def test_journal_plus_riche_que_le_courtier_est_SIGNALE_jamais_corrige():
    """Un écart négatif dit autre chose (historique tronqué, lots fantômes).
    Supprimer des lots pour faire coller les chiffres ne répare rien."""
    ordres = [_achat("QQQ", 10, 500.0, "2026-08-01T10:00:00Z")]
    a_creer, en_trop = ouvertures_manquantes(ordres, {"QQQ": 40.0})
    assert a_creer == []
    assert en_trop == [{"symbole": "QQQ", "achete": 10.0, "journal": 40.0}]


def test_courtier_muet_ne_produit_aucune_correction():
    """Un silence n'est pas une mesure : rien à écrire."""
    assert ouvertures_manquantes([], {"QQQ": 40.0}) == ([], [])


def test_idempotence_apres_application():
    """Le lot créé compte ensuite comme journalisé : le 2e passage ne propose rien."""
    ordres = [_achat("PATH", 100, 10.0, "2026-08-01T10:00:00Z"),
              _achat("PATH", 100, 20.0, "2026-08-05T10:00:00Z")]
    a_creer, _ = ouvertures_manquantes(ordres, {"PATH": 100.0})
    apres = 100.0 + sum(x["qty"] for x in a_creer)
    assert ouvertures_manquantes(ordres, {"PATH": apres}) == ([], [])


def test_deux_courtiers_ne_se_melangent_pas_dans_la_place():
    """La place du lot vient du fill non couvert, pas d'un choix par défaut."""
    ordres = [_achat("AVAX/USDC", 50, 20.0, "2026-08-01T10:00:00Z", broker="Bitmart")]
    a_creer, _ = ouvertures_manquantes(ordres, {})
    assert a_creer[0]["venue"] == "Bitmart"
