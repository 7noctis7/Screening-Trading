"""Le rejeu FIFO des fills du courtier : il reconstruit, il n'invente pas.

CE QUE CES TESTS TIENNENT. Que l'appariement suit l'ordre d'ACHAT (sinon le prix de
revient, donc le réalisé, dépend de l'ordre de parcours), qu'une vente qui déborde les
lots est NOMMÉE au lieu d'être absorbée, que le rejeu est indépendant de l'ordre dans
lequel le courtier rend ses ordres, et que la confrontation à l'inventaire réel — la
seule validation qui compte — attrape un écart.
"""

from __future__ import annotations

from packages.research.reconstruction_journal import confronter, rejouer


def _f(oid, sym, side, qty, prix, date):
    return {"id": oid, "symbol": sym, "side": side, "qty": qty, "price": prix,
            "date": date}


def test_une_vente_consomme_les_lots_du_plus_ANCIEN_au_plus_recent():
    """Deux achats à 10 puis 20, une vente de 1 à 30 : le réalisé vaut +20 (lot à 10),
    pas +10. Apparier au dernier achat flatte ou pénalise selon la tendance, et rend le
    chiffre dépendant d'un choix que personne n'a fait exprès."""
    r = rejouer([_f("1", "AAA", "buy", 1, 10.0, "2026-01-01"),
                 _f("2", "AAA", "buy", 1, 20.0, "2026-01-02"),
                 _f("3", "AAA", "sell", 1, 30.0, "2026-01-03")])
    assert len(r.fermes) == 1
    assert r.fermes[0]["entree_prix"] == 10.0
    assert r.realise == 20.0
    assert r.quantites_ouvertes() == {"AAA": 1.0}


def test_une_vente_qui_solde_TROIS_achats_produit_TROIS_trades():
    """Les prix d'entrée diffèrent ; les moyenner effacerait la seule information que ce
    registre existe pour porter."""
    r = rejouer([_f("1", "B", "buy", 1, 10.0, "2026-01-01"),
                 _f("2", "B", "buy", 1, 12.0, "2026-01-02"),
                 _f("3", "B", "buy", 1, 14.0, "2026-01-03"),
                 _f("4", "B", "sell", 3, 20.0, "2026-01-04")])
    assert len(r.fermes) == 3
    assert [t["entree_prix"] for t in r.fermes] == [10.0, 12.0, 14.0]
    assert r.realise == 24.0            # 10 + 8 + 6
    assert r.quantites_ouvertes() == {}


def test_une_vente_SANS_lot_est_nommee_jamais_absorbee():
    """C'est le signe que l'historique récupéré est TRONQUÉ. La taire produirait un
    réalisé faux sans que rien ne le signale — le défaut exact qu'on est en train de
    corriger."""
    r = rejouer([_f("1", "C", "buy", 1, 10.0, "2026-01-01"),
                 _f("2", "C", "sell", 3, 20.0, "2026-01-02")])
    assert len(r.fermes) == 1 and r.realise == 10.0
    assert r.ventes_orphelines == [
        {"symbole": "C", "qty": 2.0, "prix": 20.0, "ts": "2026-01-02", "ordre": "2"}]


def test_le_rejeu_ne_depend_PAS_de_l_ordre_rendu_par_le_courtier():
    """`AlpacaBroker.orders` rend les plus RÉCENTS d'abord. Rejouer à l'envers
    apparierait une vente à un achat POSTÉRIEUR — une chronologie impossible."""
    fills = [_f("1", "D", "buy", 2, 10.0, "2026-01-01"),
             _f("2", "D", "sell", 1, 15.0, "2026-01-05")]
    endroit, envers = rejouer(fills), rejouer(list(reversed(fills)))
    assert endroit.realise == envers.realise == 5.0
    assert endroit.quantites_ouvertes() == envers.quantites_ouvertes() == {"D": 1.0}


def test_un_fill_ILLISIBLE_est_ecarte_et_compte():
    """Un prix nul fabriquerait un prix de revient de zéro, donc un réalisé égal au
    produit de la vente. On l'écarte — et on le dit."""
    r = rejouer([_f("1", "E", "buy", 1, 0.0, "2026-01-01"),
                 _f("2", "E", "buy", 0, 10.0, "2026-01-02"),
                 _f("3", "F", "buy", 1, 10.0, "2026-01-03")])
    assert len(r.ignores) == 2
    assert r.quantites_ouvertes() == {"F": 1.0}


def test_la_CONFRONTATION_a_l_inventaire_reel_attrape_l_ecart():
    """Un rejeu qui ne retombe pas sur ce que le courtier DÉTIENT est faux, et le
    publier serait refaire l'erreur qu'on corrige."""
    r = rejouer([_f("1", "G", "buy", 5, 10.0, "2026-01-01")])
    assert confronter(r, {"G": 5.0})["conforme"] is True
    mauvais = confronter(r, {"G": 3.0, "H": 2.0})
    assert mauvais["conforme"] is False
    assert {e["symbole"] for e in mauvais["ecarts"]} == {"G", "H"}
    assert mauvais["n_symboles"] == 2


def test_UNI_slash_USD_et_UNIUSD_sont_le_MEME_instrument():
    """LE DÉFAUT DU 18/09. Le courtier emploie les DEUX graphies : la barre oblique dans
    l'historique des ordres, la forme collée dans les positions. Comparer les chaînes
    brutes faisait apparaître une position fantôme d'un côté et une absence de l'autre,
    pour un seul et même jeton — +287,86 ici, −287,22 là."""
    r = rejouer([_f("1", "UNI/USD", "buy", 287.856242, 8.9, "2026-09-18")])
    assert r.quantites_ouvertes() == {"UNIUSD": 287.856242}
    assert confronter(r, {"UNIUSD": 287.856242})["conforme"] is True


def test_les_frais_crypto_EN_NATURE_sont_nommes_pas_bloquants():
    """Les `CFEE` se prélèvent EN JETONS et n'apparaissent pas dans l'historique des
    ORDRES : un rejeu d'achats et de ventes surestime donc TOUJOURS une quantité crypto.
    On ne corrige pas le chiffre — ce serait inventer une écriture — on le nomme."""
    r = rejouer([_f("1", "UNI/USD", "buy", 287.856242, 8.9, "2026-09-18")])
    v = confronter(r, {"UNIUSD": 287.222958})      # 0,22 % de moins chez le courtier
    assert v["conforme"] is True, "un frais en nature ne doit pas bloquer l'écriture"
    assert v["ecarts"] == []
    assert len(v["frais_nature"]) == 1 and v["frais_nature"][0]["part"] < 0.01


def test_un_excedent_crypto_TROP_GROS_reste_bloquant():
    """La borne n'est pas une marge de confort : au-delà, ce n'est plus un frais."""
    r = rejouer([_f("1", "BCH/USD", "buy", 100.0, 250.0, "2026-09-18")])
    v = confronter(r, {"BCHUSD": 80.0})
    assert v["conforme"] is False and v["frais_nature"] == []


def test_un_journal_EN_DEFAUT_reste_bloquant_meme_en_crypto():
    """Le sens est imposé : les frais ne peuvent que RETIRER des jetons au courtier.
    Un journal qui en porte MOINS que le compte décrit autre chose — et bloque."""
    r = rejouer([_f("1", "ETH/USD", "buy", 1.0, 2500.0, "2026-09-18")])
    v = confronter(r, {"ETHUSD": 1.005})
    assert v["conforme"] is False and v["frais_nature"] == []
