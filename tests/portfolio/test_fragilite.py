"""Un profit factor ne dit pas si l'avantage est un avantage.

Le même 1,19 décrit un système régulier et un système dont tout le gain tient dans cinq
trades. Les deux appellent des décisions opposées : le premier se dimensionne, le second
s'arrête. Ces tests vérifient que les trois mesures les SÉPARENT.
"""

import math

import numpy as np
import pytest

from packages.portfolio.fragilite import (
    bloc_conseille,
    comparer_dimensionnement,
    concentration,
    marge_de_payoff,
    significativite,
)


# ------------------------------------------------------------------ la marge
def test_le_seuil_de_payoff_est_bien_le_point_mort():
    """À p = 1/3, il faut gagner 2 fois la perte moyenne pour ne RIEN gagner."""
    pnls = [2.0] * 100 + [-1.0] * 200
    m = marge_de_payoff(pnls)
    assert m["payoff_seuil"] == 2.0 and m["payoff"] == 2.0
    assert m["marge_payoff_pct"] == 0.0


def test_un_point_de_reussite_en_plus_vaut_plus_qu_il_n_y_parait():
    """La dérivée du seuil vaut −1/p² : près de 30 %, +1 pt de réussite abaisse le
    seuil d'environ 0,10 — le levier le plus puissant et le moins intuitif."""
    bas = marge_de_payoff([2.5] * 30 + [-1.0] * 70)["payoff_seuil"]
    haut = marge_de_payoff([2.5] * 31 + [-1.0] * 69)["payoff_seuil"]
    assert bas - haut == pytest.approx(0.10, abs=0.02)


# --------------------------------------------------------- la concentration
def test_retirer_les_cinq_meilleurs_peut_faire_basculer_sous_UN():
    """Le cas qui motive la mesure : profit factor > 1, mais porté par cinq trades."""
    pnls = [50.0] * 5 + [1.0] * 100 + [-1.0] * 140
    c = concentration(pnls)
    assert (sum(v for v in pnls if v > 0) / 140) > 1.0        # profit factor > 1
    assert c["profit_factor_sans_top5"] < 1.0        # sans eux, système perdant
    assert c["net_sans_top5"] < 0


def test_un_systeme_regulier_ne_bouge_pas_quand_on_retire_les_cinq_meilleurs():
    """Contre-épreuve : sans elle, le test précédent ne prouverait rien."""
    pnls = [2.0] * 200 + [-1.0] * 300
    c = concentration(pnls)
    assert c["profit_factor_sans_top5"] > 1.2
    assert c["part_top5_du_gain_brut_pct"] < 3.0


def test_le_nombre_de_gagnants_couvrant_les_pertes_est_exact():
    pnls = [10.0, 10.0, 10.0, 1.0, -5.0, -5.0, -5.0, -5.0]   # 20 de pertes
    assert concentration(pnls)["n_gagnants_couvrant_les_pertes"] == 2


# ------------------------------------------------------- la significativité
def test_la_mesure_est_CALIBREE_sur_du_bruit_pur():
    """Le test qui compte le plus, et il ne peut pas se faire sur un seul tirage.

    Une série de bruit donne parfois t = 1,6 : c'est normal, et l'exiger « proche de
    zéro » testerait la chance du seed, pas la mesure. Ce qui doit tenir est une
    propriété de CALIBRATION : sur des séries sans avantage, `p_esperance_negative` se
    répartit uniformément, donc franchit 5 % dans environ 5 % des cas — pas 30 %.
    """
    faux_positifs, ts = 0, []
    for seed in range(40):
        bruit = np.random.default_rng(seed).normal(0.0, 1.0, 400)
        s = significativite(bruit, n_boot=400, seed=seed)
        ts.append(abs(s["t_esperance"]))
        faux_positifs += s["p_esperance_negative"] < 0.05
    assert faux_positifs <= 6                    # ~5 % attendus sur 40, marge de tirage
    assert float(np.median(ts)) < 1.0            # le t reste centré sur zéro


def test_un_avantage_franc_est_detecte():
    """Contre-épreuve : la mesure doit aussi savoir conclure quand il y a de quoi."""
    x = np.random.default_rng(3).normal(0.5, 1.0, 600)
    s = significativite(x)
    assert s["t_esperance"] > 5.0 and s["p_esperance_negative"] == 0.0
    assert s["esperance_ic95"][0] > 0


def test_le_nombre_de_trades_manquants_est_coherent_avec_le_t_observe():
    """`n_trades_pour_conclure` = (2·sd/moyenne)². À t = 2 pile, il vaut n."""
    x = np.random.default_rng(11).normal(0.3, 1.0, 400)
    s = significativite(x)
    attendu = (2.0 / (s["t_esperance"] / math.sqrt(400))) ** 2
    assert s["n_trades_pour_conclure"] == math.ceil(attendu)


def test_le_bootstrap_par_BLOCS_est_plus_prudent_sur_une_serie_dependante():
    """Des positions qui se chevauchent partagent le même choc : le tirage i.i.d.
    surestime alors la certitude. Sur une série autocorrélée, les blocs doivent élargir
    l'intervalle — c'est la seule raison de payer leur complexité."""
    rng = np.random.default_rng(5)
    x, prec = [], 0.0
    for _ in range(600):                       # AR(1) fortement autocorrélé
        prec = 0.8 * prec + rng.normal(0.05, 1.0)
        x.append(prec)
    iid = significativite(x)["esperance_ic95"]
    blocs = significativite(x, bloc=bloc_conseille(len(x)))["esperance_ic95"]
    assert (blocs[1] - blocs[0]) > (iid[1] - iid[0])


def test_sous_trente_trades_on_dit_UNCALIBRATED_plutot_qu_un_chiffre():
    s = significativite([1.0, -1.0] * 10)
    assert s["significativite"] == "UNCALIBRATED" and "t_esperance" not in s


def test_le_resultat_est_reproductible():
    x = np.random.default_rng(1).normal(0.2, 1.0, 200)
    assert significativite(x) == significativite(x)


# ------------------------------------------------- robustesse d'entrée (leçon du 01/09)
def test_les_trois_mesures_acceptent_un_ndarray_et_ignorent_les_non_finis():
    """`x or []` teste la vérité de l'objet et lève sur un ndarray. Les P&L arrivent
    presque toujours sous cette forme."""
    a = np.array([2.0] * 100 + [-1.0] * 200 + [float("nan"), float("inf")])
    assert marge_de_payoff(a)["payoff_seuil"] == 2.0
    assert concentration(a)["n_gagnants_couvrant_les_pertes"] == 100
    assert significativite(a)["t_esperance"] is not None
    for vide in (None, [], np.array([])):
        assert marge_de_payoff(vide) == {} and concentration(vide) == {}


# ------------------------------------- queue épaisse RÉELLE ou loterie de taille ?
# La distinction commande la décision. Le R d'un trade est son résultat en unités de
# RISQUE ENGAGÉ ; dimensionner à risque égal rend le P&L proportionnel au R. Le t
# calculé sur les R est donc EXACTEMENT celui qu'on aurait obtenu, à signaux
# identiques, si chaque trade avait risqué le même montant.
def test_une_LOTERIE_DE_TAILLE_est_demasquee():
    """Signal régulier en R, mais deux positions énormes en dollars. En dollars le
    résultat semble tenir à quelques coups ; en R il ne tient à rien."""
    rng = np.random.default_rng(2)
    r = list(rng.normal(0.15, 1.0, 300))                  # signal régulier
    taille = [1.0] * 300
    taille[7], taille[99] = 60.0, 55.0                    # deux positions démesurées
    pnls = [ri * ti for ri, ti in zip(r, taille, strict=True)]
    d = comparer_dimensionnement(pnls, r)
    assert d["couverture_R_pct"] == 100.0
    assert d["gain_de_t_si_risque_egal_pct"] > 50         # le risque égal relève le t
    sans_top5_dollars = concentration(pnls)["profit_factor_sans_top5"]
    assert d["profit_factor_sans_top5_en_R"] > sans_top5_dollars


def test_une_QUEUE_STRUCTURELLE_n_est_pas_confondue_avec_une_loterie():
    """Contre-épreuve indispensable : quand la queue est dans le SIGNAL et non dans la
    taille, le risque égal ne change rien et la mesure doit le dire."""
    rng = np.random.default_rng(2)
    r = list(rng.normal(0.10, 1.0, 300))
    r[7], r[99] = 40.0, 35.0                              # la queue est dans le signal
    pnls = list(r)                                        # taille constante
    d = comparer_dimensionnement(pnls, r)
    # rien à gagner au redimensionnement : la queue est dans le signal
    assert abs(d["gain_de_t_si_risque_egal_pct"]) < 1e-6


def test_un_R_trop_peu_renseigne_dit_UNCALIBRATED():
    """Mandat données-réelles : sans couverture suffisante, pas de chiffre publié."""
    pnls = [1.0] * 100
    r = [1.0] * 50 + [None] * 50
    d = comparer_dimensionnement(pnls, r)
    assert d["dimensionnement"] == "UNCALIBRATED" and d["couverture_R_pct"] == 50.0


def test_des_series_desalignees_levent_plutot_que_de_mentir():
    """Apparier un P&L au R d'un AUTRE trade produirait un chiffre faux tout en restant
    parfaitement lisible — le pire des cas. `strict=True` l'interdit."""
    with pytest.raises(ValueError):
        comparer_dimensionnement([1.0] * 100, [1.0] * 99)
