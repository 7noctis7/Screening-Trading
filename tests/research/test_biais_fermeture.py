"""Le win rate des trades fermés est un échantillon CHOISI par la règle de sortie.

CAS CONSTRUIT, PAS CAS OBSERVÉ. Sur le compte réel du 03/09 le latent des lots ouverts
est POSITIF (+614,53 $) : le biais ne s'y est pas matérialisé. Ces tests décrivent la
configuration où il mord — part ouverte élevée ET latent négatif — pour que la mesure
existe le jour où elle se produit, plutôt que d'être déduite après coup.
"""

from packages.research.biais_fermeture import (
    marquer_lots,
    reconcilier,
    statistiques_honnetes,
    symbole_canonique,
)


def _fermes(n_gagnants: int, n_perdants: int, gain: float = 150.0,
            perte: float = -50.0) -> list[dict]:
    return ([{"pnl_net": gain, "is_win": True}] * n_gagnants
            + [{"pnl_net": perte, "is_win": False}] * n_perdants)


def test_un_lot_sans_prix_est_exclu_jamais_valorise_a_son_entree():
    """Le compter à zéro de latent fabriquerait un gagnant neutre à partir d'un trou."""
    lots = [{"symbol": "AAA", "qty": 10, "entry_price": 100.0},
            {"symbol": "BBB", "qty": 10, "entry_price": 100.0}]
    m = marquer_lots(lots, {"AAA": 90.0})
    assert m["sans_prix"] == ["BBB"]
    assert len(m["marques"]) == 1
    assert m["pnl_latent"] == -100.0


def test_le_latent_negatif_des_ouverts_effondre_l_esperance():
    """Configuration où le biais mord, chiffrée pour qu'on voie son AMPLEUR.

    Réalisé ~5 810 $ sur 39 fermés à 87 % de réussite, mais -5 720 $ de latent sur 26
    lots ouverts : total +90 $. L'espérance passe de 149 $ par trade à environ 1 $ par
    POSITION — un facteur cent, la différence entre « ça marche » et « on ne sait pas ».
    Ce n'est PAS l'état du compte réel, où le latent est positif ; c'est le scénario que
    la mesure doit attraper s'il survient.
    """
    fermes = _fermes(34, 5, gain=190.0, perte=-130.0)      # ~87 % de réussite
    lots = [{"symbol": f"S{i}", "qty": 10, "entry_price": 100.0} for i in range(26)]
    s = statistiques_honnetes(fermes, marquer_lots(lots, {f"S{i}": 78.0
                                                          for i in range(26)}))
    assert s["win_rate_ferme"] > 0.85                      # le chiffre affiché
    assert s["expectancy_ferme"] > 140                     # flatteur…
    assert s["expectancy_toutes_positions"] < 5            # …et sans lien avec le réel
    assert s["expectancy_ferme"] / s["expectancy_toutes_positions"] > 50
    assert s["pnl_total"] < 0.05 * s["pnl_realise"]        # compte quasi inchangé
    assert "biaisé vers le haut" in s["avertissement"]


def test_l_avertissement_ne_sort_que_si_les_deux_conditions_sont_reunies():
    """Un avertissement permanent cesse d'être lu : il faut les DEUX conditions."""
    fermes = _fermes(30, 5)
    # latent POSITIF, part ouverte élevée → pas d'avertissement
    lots = [{"symbol": f"S{i}", "qty": 10, "entry_price": 100.0} for i in range(20)]
    prix_haut = {f"S{i}": 120.0 for i in range(20)}
    haut = statistiques_honnetes(fermes, marquer_lots(lots, prix_haut))
    assert haut["avertissement"] == ""
    # latent NÉGATIF, part ouverte élevée → avertissement chiffré
    prix_bas = {f"S{i}": 80.0 for i in range(20)}
    bas = statistiques_honnetes(fermes, marquer_lots(lots, prix_bas))
    assert "lots ouverts" in bas["avertissement"]
    assert "biaisé vers le haut" in bas["avertissement"]


def test_aucun_lot_ouvert_laisse_les_deux_lectures_identiques():
    """Sans position ouverte, pas de sélection : les deux chiffres coïncident."""
    fermes = _fermes(15, 15)
    s = statistiques_honnetes(fermes, marquer_lots([], {}))
    assert s["expectancy_ferme"] == s["expectancy_toutes_positions"]
    assert s["win_rate_ferme"] == s["win_rate_toutes_positions"]
    assert s["avertissement"] == ""


def test_sous_vingt_fermes_rien_n_est_publie():
    s = statistiques_honnetes(_fermes(5, 3), marquer_lots([], {}))
    assert "win_rate_ferme" not in s
    assert "UNCALIBRATED" in s["statut_ferme"]


# ── Réconciliation journal ↔ courtier ────────────────────────────────────────────


def test_les_trois_conventions_de_nommage_designent_le_meme_actif():
    """Piège déjà payé en production le 27/08 (`AAVEUSD` non reconnu comme crypto).

    Comparer sans canoniser produirait des écarts entièrement fictifs sur toute la
    poche crypto — et ferait passer un vrai problème pour du bruit de nommage.
    """
    assert symbole_canonique("AVAX/USDC") == "AVAX"
    assert symbole_canonique("AVAX-USD") == "AVAX"
    assert symbole_canonique("AVAXUSD") == "AVAX"
    assert symbole_canonique("QQQ") == "QQQ"
    assert symbole_canonique("AAPL") == "AAPL"


def test_un_ticker_court_n_est_pas_amputé_par_le_suffixe():
    """« USD » lui-même ne doit pas devenir la chaîne vide."""
    assert symbole_canonique("USD") == "USD"


def test_reconciliation_verte_quand_les_quantites_concordent():
    lots = [{"symbol": "AVAX/USDC", "qty": 100.0}, {"symbol": "QQQ", "qty": 70.0}]
    r = reconcilier(lots, {"AVAXUSD": 100.0, "QQQ": 70.0})
    assert r["reconcilie"] is True and r["n_ecarts"] == 0 and r["motif"] == ""


def test_un_lot_que_le_courtier_ne_detient_pas_est_un_fantome():
    """Le cas réel du 03/09 : ~80 actions au journal, zéro sur le compte."""
    lots = [{"symbol": "AAPL", "qty": 47.3}, {"symbol": "QQQ", "qty": 137.1}]
    r = reconcilier(lots, {"QQQ": 70.45})
    assert r["reconcilie"] is False
    assert r["n_fantomes"] == 1                        # AAPL, détenu à zéro
    assert r["n_ecarts"] == 2                          # AAPL + QQQ en quantité
    assert "ne décrit pas ce compte" in r["motif"]


def test_un_ecart_de_quantite_infime_ne_declenche_rien():
    """Les fills laissent des arrondis : 1 % de tolérance, sinon l'alerte est
    permanente — et une alerte permanente cesse d'être lue."""
    r = reconcilier([{"symbol": "QQQ", "qty": 70.4520}], {"QQQ": 70.4519})
    assert r["reconcilie"] is True


# ── Le panneau montre-t-il le compte, ou un sous-ensemble favorable ? ─────────────

def test_perimetre_chiffre_ce_que_le_filtre_masque():
    """Mesuré le 03/09 : +6 260 $ affichés, +569 $ subis, l'écart tenant aux importés.
    Aucun des deux n'est faux — c'est de n'en publier qu'un qui l'était."""
    from packages.research.biais_fermeture import perimetre_affiche
    affiches = [{"exit_ts": "t", "pnl_net": 6260.82, "is_win": True}]
    tous = affiches + [{"exit_ts": "t", "pnl_net": -5691.51, "is_win": False},
                       {"exit_ts": None}]
    out = perimetre_affiche(tous, affiches)
    assert out["lots_masques"] == 2
    assert out["realise_masque"] == -5691.51
    assert out["compte"]["pnl_realise"] == 569.31
    assert out["affiche"]["win_rate"] == 1.0
    assert out["compte"]["win_rate"] == 0.5
    assert "SOUS-ENSEMBLE" in out["avertissement"]


def test_perimetre_sans_ecart_ne_crie_pas():
    """Quand le panneau montre tout, il n'y a rien à avertir."""
    from packages.research.biais_fermeture import perimetre_affiche
    rows = [{"exit_ts": "t", "pnl_net": 10.0, "is_win": True}]
    assert perimetre_affiche(rows, rows)["avertissement"] is None


def test_perimetre_espace_fine_ne_mange_pas_la_ponctuation():
    """Le séparateur de milliers ne doit remplacer QUE lui : appliquer le remplacement
    à la phrase entière effaçait ses virgules (« fills importés  sans features »)."""
    from packages.research.biais_fermeture import perimetre_affiche
    tous = [{"exit_ts": "t", "pnl_net": -5691.51, "is_win": False}]
    avert = perimetre_affiche(tous, [])["avertissement"]
    assert "-5 691.51 $" in avert
    assert "importés, sans features" in avert
