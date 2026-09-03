"""Le win rate des trades fermés est un échantillon CHOISI par la règle de sortie.

CAS CONSTRUIT, PAS CAS OBSERVÉ. Sur le compte réel du 03/09 le latent des lots ouverts
est POSITIF (+614,53 $) : le biais ne s'y est pas matérialisé. Ces tests décrivent la
configuration où il mord — part ouverte élevée ET latent négatif — pour que la mesure
existe le jour où elle se produit, plutôt que d'être déduite après coup.
"""

from packages.research.biais_fermeture import (
    marquer_lots,
    statistiques_honnetes,
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
