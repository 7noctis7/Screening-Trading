"""Banc swing : les trois règles qui décident du résultat, et la preuve d'anti-fuite."""

from dataclasses import dataclass

from packages.backtest.banc_swing import bilan, parcourir, simuler_trade


@dataclass
class B:
    open: float
    high: float
    low: float
    close: float
    volume: float = 1000.0


def _plat(n, px=100.0):
    return [B(px, px + 0.5, px - 0.5, px) for _ in range(n)]


def test_l_entree_est_une_LIMITE_pas_un_marche():
    """Entrer « au marché à la clôture de détection » offrirait un prix que le marché n'a
    pas donné, et transformerait CHAQUE signal en trade — ce qui gonfle le nombre
    d'observations, donc la significativité apparente."""
    barres = [*_plat(3), B(100, 100.4, 99.6, 100), B(100, 100.4, 99.6, 100)]
    # limite à 95 : jamais touchée sur la fenêtre → aucun trade, pas un trade au marché
    assert simuler_trade(barres, 0, "long", 95.0, 93.0, 99.0) is None


def test_la_limite_touchee_entre_au_prix_NOMME():
    barres = [B(100, 100, 100, 100), B(99, 99.5, 94.0, 95), B(96, 99.5, 95.5, 99)]
    t = simuler_trade(barres, 0, "long", 95.0, 93.0, 99.0)
    assert t and t["i_entree"] == 1


def test_stop_ET_cible_dans_la_MEME_barre_donne_le_STOP():
    """Une barre journalière ne dit pas l'ordre de ses extrêmes. Choisir la cible, c'est
    choisir la version favorable d'une information qu'on n'a pas — et sur un RR > 1, ce
    seul choix suffit à faire passer un banc du rouge au vert."""
    # la barre 1 touche l'entrée 95, le stop 93 ET la cible 99
    barres = [B(100, 100, 100, 100), B(99, 99.5, 92.5, 96)]
    t = simuler_trade(barres, 0, "long", 95.0, 93.0, 99.0)
    assert t["sortie"] == "stop" and t["r"] == -1.0


def test_le_resultat_est_en_R():
    """Un R = la distance entrée-stop. Seule unité comparable entre actifs."""
    barres = [B(100, 100, 100, 100), B(99, 99.5, 94.9, 95),
              B(96, 101.5, 95.5, 101)]
    t = simuler_trade(barres, 0, "long", 95.0, 93.0, 99.0)   # risque 2, gain 4
    assert t["sortie"] == "cible" and t["r"] == 2.0


def test_un_short_se_mesure_dans_le_BON_sens():
    """Contrôle NÉGATIF du signe : un banc qui inverse le short affiche l'exact opposé
    de la performance, et le total reste plausible."""
    barres = [B(100, 100, 100, 100), B(100, 105.1, 99, 105),
              B(105, 105, 100.9, 101)]
    t = simuler_trade(barres, 0, "short", 105.0, 107.0, 101.0)  # risque 2, gain 4
    assert t["sortie"] == "cible" and t["r"] == 2.0


def test_sans_sortie_on_solde_a_l_HORIZON():
    barres = [B(100, 100, 100, 100), B(99, 99.5, 94.9, 95), *_plat(4, 96.0)]
    t = simuler_trade(barres, 0, "long", 95.0, 93.0, 120.0, horizon=3)
    assert t["sortie"] == "horizon" and t["r"] == 0.5      # +1 sur un risque de 2


def test_le_detecteur_ne_recoit_QUE_LE_PASSE():
    """LA garantie anti-fuite, et elle est structurelle : `parcourir` tronque les barres
    à `i`. Même un détecteur qui lirait `barres[i+5]` ne les aurait pas. On ne fait pas
    confiance à la lecture du code — on retire l'accès, et on le vérifie."""
    barres = _plat(70)
    vus: list[int] = []

    def espion(_sym, b, i):
        vus.append(len(b) - 1 - i)      # 0 si la dernière barre reçue EST la barre i
        return {"propositions": []}

    parcourir("X", barres, espion, depart=60)
    assert vus and set(vus) == {0}, f"le détecteur a vu au-delà de i : {set(vus)}"


def test_un_detecteur_TRICHEUR_serait_neutralise():
    """Contrôle NÉGATIF du test précédent : un détecteur qui tente de lire l'avenir doit
    échouer, pas réussir silencieusement. Sans lui, `vus == {0}` pourrait passer au vert
    sur un `parcourir` qui n'appelle jamais le détecteur."""
    barres = _plat(65)
    tentatives = {"hors_borne": 0}

    def tricheur(_sym, b, i):
        try:
            _ = b[i + 5]
        except IndexError:
            tentatives["hors_borne"] += 1
        return {"propositions": []}

    parcourir("X", barres, tricheur, depart=60)
    assert tentatives["hors_borne"] > 0


def test_le_bilan_dit_UNCALIBRATED_sans_trade():
    """Zéro trade n'est pas une espérance de zéro : c'est une absence de mesure."""
    b = bilan([])
    assert b["n"] == 0 and "UNCALIBRATED" in b["statut"]
    assert "esperance_r" not in b


def test_le_bilan_compte_les_sorties_par_type():
    trades = [{"r": 2.0, "sortie": "cible"}, {"r": -1.0, "sortie": "stop"},
              {"r": -1.0, "sortie": "stop"}, {"r": 0.3, "sortie": "horizon"}]
    b = bilan(trades)
    assert b["n"] == 4 and b["par_sortie"] == {"stop": 2, "cible": 1, "horizon": 1}
    assert b["taux_reussite"] == 0.5 and b["total_r"] == 0.3
