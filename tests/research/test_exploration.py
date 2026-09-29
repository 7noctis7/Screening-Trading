"""Banc d'exploration pré-enregistré — ce qui doit tenir pour que le classement ne mente pas.

Classer des centaines de scénarios sur le même historique puis retenir le premier est la
fabrique de faux positifs par excellence. Le banc n'est honnête que si : (1) chaque règle
est CAUSALE, (2) l'exécution suit la décision, (3) la grille est figée par une empreinte,
(4) chaque scénario compte dans N, (5) la période cachée ne se lit qu'UNE fois.
"""

from __future__ import annotations

import numpy as np
import pytest


def _prix(n=12, T=600, graine=0, derive=0.0003):
    rng = np.random.default_rng(graine)
    return 50 * np.exp(np.cumsum(rng.normal(derive, 0.015, (n, T)), axis=1))


# ------------------------------------------------------------------ règles causales

@pytest.mark.parametrize("selection", ["tout", "mom_12_1", "mom_6_1", "basse_vol",
                                       "tendance_mm200"])
@pytest.mark.parametrize("ponderation", ["egal", "inv_vol", "erc"])
def test_les_poids_a_t_ne_dependent_que_du_passe(selection, ponderation):
    from packages.research.explo_regles import poids_a_la_date
    A = _prix()
    t = 400
    futur_modifie = A.copy()
    futur_modifie[:, t + 1:] *= 3.0                          # l'avenir change du tout au tout
    regle = {"selection": selection, "ponderation": ponderation, "overlay": "aucun",
             "top_k": 5}
    w1 = poids_a_la_date(A, t, regle, par_an=252.0)
    w2 = poids_a_la_date(futur_modifie, t, regle, par_an=252.0)
    assert np.allclose(w1, w2)
    assert w1.sum() <= 1.0 + 1e-9 and (w1 >= -1e-12).all()


def test_regime_coupe_l_exposition_sous_la_mm200():
    from packages.research.explo_regles import poids_a_la_date
    A = np.vstack([np.linspace(100, 50, 400)] * 4)           # marché qui baisse
    w = poids_a_la_date(A, 399, {"selection": "tout", "ponderation": "egal",
                                 "overlay": "regime_mm200", "top_k": 4}, par_an=252.0)
    assert w.sum() == 0.0


# ------------------------------------------------------------------ moteur

def test_execution_a_la_barre_suivante():
    """Décidé au close t, exécuté au close t+1 : le saut de la barre de décision n'est pas
    capturé."""
    from packages.research.explo_moteur import simuler
    A = np.ones((1, 10)) * 100.0
    A[0, 5:] = 150.0                                          # saut entre la barre 4 et 5
    r = simuler(A, lambda t: np.array([1.0]), pas=100, couts=np.zeros(1), debut=4, fin=9)
    assert np.allclose(r["rendements"], 0.0)                  # acheté à 150, jamais à 100


def test_frais_sur_le_turnover():
    from packages.research.explo_moteur import simuler
    A = np.ones((2, 6)) * 100.0
    poids = iter([np.array([1.0, 0.0]), np.array([0.0, 1.0])])
    r = simuler(A, lambda t: next(poids), pas=2, couts=np.array([0.001, 0.001]),
                debut=0, fin=5)
    assert r["frais"] == pytest.approx(0.001 + 0.002)         # entrée, puis rotation complète


# ------------------------------------------------------------------ grille

GRILLE = {"nom": "test", "fin_in_sample": "2020-12-31", "timeframe": "1d",
          "univers": ["qqq", "actions_us"], "selections": ["tout", "mom_12_1"],
          "ponderations": ["egal", "erc"], "overlays": ["aucun", "vol_cible_15"],
          "pas": {"jour": 1, "mois": 21}, "top_k": 5}


def test_expansion_de_la_grille():
    from packages.research.explo_grille import scenarios
    sc = scenarios(GRILLE)
    ids = [s["id"] for s in sc]
    assert len(ids) == len(set(ids))
    # qqq : un seul actif → sélection/pondération sans objet : overlays × pas = 4
    assert sum(1 for s in sc if s["univers"] == "qqq") == 4
    assert len(scenarios({**GRILLE, "univers": ["btc"]})) == 4
    # actions_us : « tout » exclut ERC (trop de titres) → (tout·egal + mom·egal + mom·erc) × 2 × 2
    assert sum(1 for s in sc if s["univers"] == "actions_us") == 3 * 2 * 2


def test_empreinte_stable_et_sensible():
    from packages.research.explo_grille import empreinte
    assert empreinte(GRILLE) == empreinte(dict(reversed(list(GRILLE.items()))))
    assert empreinte(GRILLE) != empreinte({**GRILLE, "top_k": 6})


def test_la_periode_cachee_ne_se_lit_qu_une_fois(tmp_path):
    from packages.research.explo_grille import consommer_holdout, holdout_deja_lu
    reg = tmp_path / "holdout.jsonl"
    assert not holdout_deja_lu("abc", reg)
    consommer_holdout("abc", ["s1"], reg)
    assert holdout_deja_lu("abc", reg)
    with pytest.raises(RuntimeError):
        consommer_holdout("abc", ["s2"], reg)


def test_classement_deflate_par_le_nombre_de_scenarios():
    """Sur du bruit pur, aucun scénario ne doit sortir avec un DSR élevé."""
    from packages.research.explo_grille import classer
    rng = np.random.default_rng(3)
    R = rng.normal(0.0, 0.01, (1000, 200))                    # 200 scénarios sans edge
    lignes = [{"id": f"s{k}"} for k in range(200)]
    classes, pbo = classer(lignes, R, par_an=252.0, n_anterieurs=0)
    assert classes[0]["dsr"] < 0.95
    assert pbo.get("available")


def test_le_ledger_compte_chaque_scenario(tmp_path):
    from packages.research.ledger import append_record, deflation_params
    p = tmp_path / "h.jsonl"
    append_record({"facteur": "a"}, p)
    append_record({"facteur": "exploration:x", "n_essais": 500}, p)
    n, _ = deflation_params(p)
    assert n == 501


# ------------------------------------------------------------------ bout en bout

def _donnees_factices(T=700):
    A = _prix(n=15, T=T, graine=5)
    noms = ["QQQ"] + [f"T{k}" for k in range(14)]
    dates = [f"2019-{1 + k // 28:02d}-{1 + k % 28:02d}" for k in range(T)]
    return {"noms": noms, "dates": dates, "A": A,
            "acmap": {s: ("etf" if s == "QQQ" else "equity") for s in noms},
            "devise": {s: "USD" for s in noms}, "mode": "test"}


def test_executer_n_atteint_jamais_la_periode_cachee():
    """Les rendements en échantillon ne changent pas si la période cachée change."""
    from packages.research.explo_donnees import executer
    from packages.research.explo_grille import scenarios
    d = _donnees_factices()
    scs = scenarios({**GRILLE, "overlays": ["aucun", "regime_mm200"]})
    R1, l1 = executer(d, scs, 300, 500, 252.0, bavard=False)
    d2 = {**d, "A": d["A"].copy()}
    d2["A"][:, 501:] *= 0.2                                   # krach dans la période cachée
    R2, _ = executer(d2, scs, 300, 500, 252.0, bavard=False)
    assert R1.shape == (200, len(scs)) and len(l1) == len(scs)
    assert np.allclose(R1, R2)


def test_membres_des_univers():
    from packages.research.explo_donnees import membres
    noms = ["BTC/USDC", "ETH/USDC", "QQQ", "AAPL", "SAP", "GLD"]
    ac = {"BTC/USDC": "crypto", "ETH/USDC": "crypto", "QQQ": "etf", "AAPL": "equity",
          "SAP": "equity", "GLD": "etf"}
    dv = {"AAPL": "USD", "SAP": "EUR"}
    assert membres("btc", noms, ac, dv) == [0]
    assert membres("actions_us", noms, ac, dv) == [3]
    assert membres("multi_actifs", noms, ac, dv) == [0, 2, 5]
    assert membres("crypto", noms, ac, dv) == [0, 1]


def test_les_grilles_du_depot_se_developpent():
    from pathlib import Path

    import yaml

    from packages.research.explo_grille import scenarios
    for p in sorted(Path("config/exploration").glob("*.yaml")):
        g = yaml.safe_load(p.read_text(encoding="utf-8"))
        sc = scenarios(g)
        assert len(sc) == len({s["id"] for s in sc}) > 0, p
