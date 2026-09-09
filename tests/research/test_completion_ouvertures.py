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


def test_prix_du_manquant_vient_des_fills_NON_couverts():
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


def test_fill_coupe_en_deux_garde_SON_prix_et_SA_date():
    """60 connues sur un premier fill de 100 : les 40 restantes gardent SON prix, et le
    fill du lendemain reste un lot SÉPARÉ, à sa date et à son prix.

    Ce test portait la version fusionnée : UN lot de 140 unités à 24,29 $ daté du 08-01.
    Or au 08-01 il n'existait que 40 unités, à 10 $ — les 100 autres sont arrivées le
    lendemain à 30 $. Ce lot n'a jamais existé, et le FIFO le fermait EN PREMIER contre
    des ventes réelles."""
    ordres = [_achat("SOL/USDC", 100, 10.0, "2026-08-01T10:00:00Z"),
              _achat("SOL/USDC", 100, 30.0, "2026-08-02T10:00:00Z")]
    a_creer, _ = ouvertures_manquantes(ordres, {"SOL": 60.0})

    assert [(round(x["qty"], 6), x["prix"], x["date"][:10]) for x in a_creer] == [
        (40.0, 10.0, "2026-08-01"), (100.0, 30.0, "2026-08-02")]
    assert sum(x["qty"] for x in a_creer) == 140.0     # la quantité, elle, est conservée


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


def test_pas_de_perte_FABRIQUEE_sur_un_actif_qui_monte():
    """RÉGRESSION du 09/09, mesurée sur le compte réel. Le biais était STRUCTUREL.

    Le FIFO consomme les fills les plus ANCIENS : le reste non couvert est donc fait des
    plus RÉCENTS — les plus CHERS sur un actif qui monte — tout en étant daté du plus
    ancien d'entre eux. Le lot fusionné portait le prix des uns et la date des autres, et
    le FIFO le fermait en premier. Sur le compte : BTC reconstitué à 76 801 $ daté du
    07-07, fermé le 07-08 à 61 731 $ — -19,6 % en une nuit qui n'existe pas sur la
    courbe. ETH -29,1 % et LTC -13,1 % la même nuit, -3 140 $ à eux trois.

    Ici : 1 unité connue, achetée à 100 en janvier ; 2 manquantes, à 100 et 200. La
    fusion produisait 2 unités à 150 datées de FÉVRIER — donc un coût de revient de 150
    pour une unité qui en a coûté 100. La version corrigée date chaque unité de son
    propre fill : aucune n'est vendue à perte contre un prix qu'elle n'a pas payé.
    """
    ordres = [_achat("BTC/USD", 1, 100.0, "2026-01-01T10:00:00Z"),
              _achat("BTC/USD", 1, 100.0, "2026-02-01T10:00:00Z"),
              _achat("BTC/USD", 1, 200.0, "2026-03-01T10:00:00Z")]
    a_creer, _ = ouvertures_manquantes(ordres, {"BTC": 1.0})

    assert len(a_creer) == 2, "les fills restants ne doivent plus être fusionnés"
    # le lot le PLUS ANCIEN — celui que le FIFO fermera d'abord — porte SON vrai prix
    premier = min(a_creer, key=lambda x: x["date"])
    assert premier["prix"] == 100.0 and premier["date"][:7] == "2026-02"
    # et aucun lot ne porte le VWAP fusionné (150), qu'aucun fill n'a jamais payé
    assert 150.0 not in {x["prix"] for x in a_creer}


def test_chaque_lot_reconstitue_a_un_identifiant_DISTINCT():
    """Plusieurs lots par symbole : une clé au seul symbole les écraserait entre eux et
    n'en garderait qu'un — la moitié du coût de revient disparaîtrait en silence."""
    import importlib.util
    from pathlib import Path as _P

    spec = importlib.util.spec_from_file_location(
        "_co", _P(__file__).resolve().parents[2] / "scripts" / "completer_ouvertures.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    ordres = [_achat("BTC/USD", 1, 100.0, "2026-01-01T10:00:00Z"),
              _achat("BTC/USD", 1, 200.0, "2026-03-01T10:00:00Z")]
    a_creer, _ = ouvertures_manquantes(ordres, {})

    ids = [mod._record(lot).id for lot in a_creer]
    assert len(set(ids)) == len(ids) == 2, ids
    # déterministe : rejouer le même plan REDONNE les mêmes clés (donc un UPSERT)
    assert [mod._record(lot).id for lot in a_creer] == ids


def test_un_lot_au_prix_que_le_marche_n_a_pas_cote_est_REFUSE():
    """Le contrôle qui manquait le 09/09. Il existait — `diag_journal_compte` compare le
    prix d'entrée de chaque lot à la clôture de son jour — mais il tournait APRÈS
    l'écriture : il a constaté le dégât au lieu de l'empêcher."""
    from packages.research.completion_ouvertures import lots_incoherents

    plan = [{"symbole": "BTC", "date": "2026-07-07T10:00:00Z", "prix": 76801.0,
             "qty": 0.1},
            {"symbole": "QQQ", "date": "2026-07-07T10:00:00Z", "prix": 500.0,
             "qty": 10.0}]
    cours = {"BTC": 61731.0, "QQQ": 498.0}.get

    hors = lots_incoherents(plan, lambda s, _d: cours(s))
    assert [x["symbole"] for x in hors] == ["BTC"]          # +24 % : refusé
    assert abs(hors[0]["ecart"] - (76801.0 / 61731.0 - 1)) < 1e-9
    # QQQ à +0,4 % passe : un fill s'exécute dans la journée, pas à la clôture pile


def test_une_base_de_prix_MUETTE_ne_condamne_aucun_lot():
    """Fail-closed sur l'incohérence, pas sur l'absence. Bloquer une réparation parce
    que la base de prix ne répond pas, c'est transformer un silence en verdict."""
    from packages.research.completion_ouvertures import lots_incoherents

    plan = [{"symbole": "BTC", "date": "2026-07-07T10:00:00Z", "prix": 76801.0,
             "qty": 0.1}]
    assert lots_incoherents(plan, lambda _s, _d: None) == []
    assert lots_incoherents(plan, lambda _s, _d: 0.0) == []


def test_le_plan_CORRIGE_passe_le_controle_de_coherence():
    """Boucle la démonstration : un lot par fill porte le prix de SA date, donc le
    contrôle qui refuse la version fusionnée laisse passer la version juste."""
    from packages.research.completion_ouvertures import lots_incoherents

    ordres = [_achat("BTC/USD", 1, 100.0, "2026-01-01T10:00:00Z"),
              _achat("BTC/USD", 1, 100.0, "2026-02-01T10:00:00Z"),
              _achat("BTC/USD", 1, 200.0, "2026-03-01T10:00:00Z")]
    a_creer, _ = ouvertures_manquantes(ordres, {"BTC": 1.0})

    marche = {"2026-02": 100.0, "2026-03": 200.0}          # le marché de chaque date
    assert lots_incoherents(a_creer, lambda _s, d: marche[d[:7]]) == []
