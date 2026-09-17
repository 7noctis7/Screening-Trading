"""Le périmètre du panneau se lit sur l'ORIGINE du lot, plus sur `legacy`.

CE QUI A ÉTÉ MESURÉ (17/09). `/api/journal` lisait `all(legacy=False)`. Mais `legacy`
répond à « ce trade porte-t-il les features de décision ? » — la question de la
calibration ML. Un ordre RÉELLEMENT PASSÉ par le robot, journalisé après coup depuis le
fill du courtier (`completer_ouvertures`), vaut `legacy=1` : le filtre l'écartait. Le
panneau affichait **+139,75 $ sur 62 trades** quand le robot avait fait **−23,15 $ sur
112**. Le chiffre n'était pas faux ; il décrivait un sous-ensemble, et ce sous-ensemble
était favorable parce que les pertes non appariées en étaient absentes.

CE QUE CES TESTS TIENNENT : les deux préfixes du robot entrent, l'import historique
reste dehors, les tranches d'une vente partielle suivent leur lot, et un préfixe
INCONNU est compté et nommé plutôt qu'écarté en silence.
"""

from __future__ import annotations

from packages.execution.perimetre_journal import (
    IMPORT,
    INCONNU,
    ROBOT,
    origine,
    pris_par_le_robot,
    ventiler,
)


def test_les_deux_ecritures_du_ROBOT_entrent_dans_le_perimetre():
    """`P-` est la décision journalisée, `C-` le même ordre reconstitué du fill réel.

    Les distinguer ici reviendrait à refaire le tri par `legacy` sous un autre nom.
    """
    assert pris_par_le_robot("P-20260915-Alpaca-VZ")
    assert pris_par_le_robot("C-OSCR-4dfb61cb")
    assert origine("P-20260915-Alpaca-VZ") == ROBOT
    assert origine("C-MPC-fd227cb7") == ROBOT


def test_l_import_historique_reste_DEHORS():
    """Aucun script du dépôt n'écrit `LEG-` : l'import qui l'a produit n'est plus dans
    l'arbre, et deux symboles y portent jusqu'à 1,9 fois leur achat. Une provenance
    qu'on ne peut pas lire ne se compte pas comme une décision du robot."""
    assert not pris_par_le_robot("LEG-ad4ac9fa7f59")
    assert origine("LEG-ad4ac9fa7f59") == IMPORT


def test_les_TRANCHES_suivent_leur_lot():
    """Une vente partielle suffixe l'identifiant (`-Xn` dans `live_roundtrip`, `-Rn`
    dans `reconcilier_journal`). Comparer l'identifiant ENTIER ferait disparaître du
    périmètre la moitié des fermetures — celles, justement, qui portent le P&L."""
    assert pris_par_le_robot("P-20260915-Alpaca-OSCR-R1")
    assert pris_par_le_robot("C-OKTA-8a85b246-R2")
    assert pris_par_le_robot("P-20260910-Alpaca-VZ-X2")
    assert not pris_par_le_robot("LEG-ad4ac9fa7f59-R3")


def test_un_prefixe_INCONNU_est_compte_et_nomme_jamais_avale():
    """Le seul mode de défaillance qu'on ne sait pas mesurer, c'est le silence. Si un
    script introduit demain un quatrième préfixe, il doit APPARAÎTRE — en périmètre ou
    hors périmètre, mais nommé, pas absorbé par un `else`."""
    assert origine("Z-nouveau-truc-42") == INCONNU
    assert origine("") == INCONNU
    assert origine(None) == INCONNU

    v = ventiler([{"id": "Z-nouveau-truc-42", "exit_ts": "2026-09-17",
                   "pnl_net": 10.0}])
    assert v[INCONNU]["n"] == 1
    assert v[ROBOT]["n"] == 0
    assert "Z-nouveau-truc-42" in v["inconnus"]


def test_la_ventilation_separe_le_realise_par_origine():
    """C'est ce chiffre qui rend le sous-ensemble LISIBLE comme un sous-ensemble : sans
    lui, le lecteur ne peut pas juger de ce qu'il ne voit pas."""
    lots = [
        {"id": "P-1", "exit_ts": "2026-09-17", "pnl_net": 100.0},
        {"id": "C-2", "exit_ts": "2026-09-17", "pnl_net": -40.0},
        {"id": "P-3", "exit_ts": None, "pnl_net": None},      # ouvert : pas de réalisé
        {"id": "LEG-4", "exit_ts": "2026-09-17", "pnl_net": -900.0},
    ]
    v = ventiler(lots)
    assert v[ROBOT] == {"n": 3, "n_fermes": 2, "pnl_realise": 60.0}
    assert v[IMPORT] == {"n": 1, "n_fermes": 1, "pnl_realise": -900.0}
    assert v["inconnus"] == []
