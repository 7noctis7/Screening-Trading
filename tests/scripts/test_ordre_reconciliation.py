"""Le portail refusait des achats financés par des ventes du MÊME lot.

CE QUE CE TEST PROTÈGE. `_reconcile` parcourait les lignes par cible décroissante. Une
ligne à solder ayant une cible de ZÉRO, elle passait en dernier — donc le portail de
risque évaluait chaque achat en voyant encore, dans l'exposition brute, tout ce que le
lot s'apprêtait à liquider.

Le cas ci-dessous transcrit EXACTEMENT le run paper du 14/09/2026 (VPS, Alpaca).
Brut 80 785 $ pour un plafond de 100 194 $ ; 19 408 $ d'achats acceptés
saturent le plafond ; sept achats sont refusés pour 9 961 $ — puis sept lignes sont
soldées,
libérant 13 720 $. L'argent était là ; il arrivait trop tard.

Conséquence visible : 57 180 $ immobilisés en liquidités, et huit lignes cibles jamais
achetées. Rien dans l'interface ne disait pourquoi.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]


def _module():
    spec = importlib.util.spec_from_file_location(
        "run_live_sous_test", RACINE / "scripts" / "run_live.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── le run réel du 14/09, ligne à ligne ──────────────────────────────────────
ACHATS = {"TRV": (4369, 2915), "TEN": (4369, 2861), "MPC": (4369, 2866),
          "OSCR": (4369, 2913), "THC": (4212, 0), "MCK": (3945, 0),
          "VZ": (3825, 2515), "HPQ": (3558, 0), "LNC": (2811, 0),
          "NWS": (2784, 0), "SIG": (2645, 1992), "T": (2406, 1644)}
VENTES = {"DUOL": (0, 1342), "LINKUSD": (0, 1456), "NWSA": (0, 1816),
          "OXY": (0, 2860), "PATH": (0, 1865), "PSX": (0, 2863),
          "SOLUSD": (0, 1518)}


def _cas():
    tgt, detenu = {}, {}
    for sym, (cible, tenu) in {**ACHATS, **VENTES}.items():
        tgt[sym] = {"val": float(cible), "sym": sym, "o": None}
        detenu[sym] = float(tenu)
    return tgt, detenu


def _ordre(mod):
    tgt, detenu = _cas()
    return [k for k, _ in mod.ordre_de_traitement(tgt, detenu)]


def test_toutes_les_ventes_precedent_tous_les_achats():
    ordre = _ordre(_module())
    derniere_vente = max(ordre.index(s) for s in VENTES)
    premier_achat = min(ordre.index(s) for s in ACHATS)
    assert derniere_vente < premier_achat


def test_les_sept_liquidations_du_14_09_passent_en_tete():
    assert set(_ordre(_module())[:7]) == set(VENTES)


def test_l_exposition_liberee_couvre_les_achats_qui_etaient_refuses():
    """Le chiffre qui justifie le correctif : 13 720 $ libérés, 9 961 $ refusés."""
    libere = sum(tenu - cible for cible, tenu in VENTES.values())
    refuses = {"LNC": 2811, "NWS": 2784, "SIG": 653, "T": 762}   # actions refusées
    refuses_crypto = 1119 + 1013 + 818                            # LTC + ETH + BCH
    assert libere == 13720
    assert libere > sum(refuses.values()) + refuses_crypto


def test_les_ventes_sont_triees_de_la_plus_grosse_a_la_plus_petite():
    ordre = _ordre(_module())[:7]
    montants = [VENTES[s][1] - VENTES[s][0] for s in ordre]
    assert montants == sorted(montants, reverse=True)


def test_l_ordre_entre_achats_reste_celui_d_avant():
    """Le correctif déplace les ventes ; il ne rebat pas les cartes entre achats."""
    ordre = [s for s in _ordre(_module()) if s in ACHATS]
    attendu = sorted(ACHATS, key=lambda s: -ACHATS[s][0])
    assert ordre == attendu


def test_une_ligne_deja_a_sa_cible_ne_passe_pas_devant_les_ventes():
    """Delta nul : ce n'est pas une vente, donc elle reste dans le groupe des achats.

    Elle y garde sa place au tri par cible décroissante — un delta nul ne produira de
    toute façon aucun ordre. Ce qui compte est qu'elle ne s'insère pas AVANT la vente.
    """
    mod = _module()
    tgt = {"A": {"val": 1000.0}, "B": {"val": 0.0}, "C": {"val": 500.0}}
    tenu = {"A": 1000.0, "B": 900.0, "C": 0.0}
    ordre = [k for k, _ in mod.ordre_de_traitement(tgt, tenu)]
    assert ordre == ["B", "A", "C"]       # vente, puis achats par cible décroissante


def test_sans_aucune_vente_l_ordre_est_inchange():
    mod = _module()
    tgt = {"X": {"val": 300.0}, "Y": {"val": 900.0}, "Z": {"val": 600.0}}
    assert [k for k, _ in mod.ordre_de_traitement(tgt, {})] == ["Y", "Z", "X"]


def test_une_ligne_inconnue_du_detenu_vaut_zero_pas_une_erreur():
    mod = _module()
    assert [k for k, _ in mod.ordre_de_traitement({"N": {"val": 10.0}}, {})] == ["N"]
