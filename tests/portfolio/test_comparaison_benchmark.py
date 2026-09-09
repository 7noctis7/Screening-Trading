"""Portefeuille vs références : alignement sans look-ahead, rebasage en dollars."""

from packages.portfolio.comparaison_benchmark import (
    aligner,
    comparaison,
    performance,
    serie_totale,
)

PF = [{"t": "2026-06-22", "v": 100_000.0},
      {"t": "2026-06-27", "v": 102_000.0},      # un SAMEDI : les actions ne cotent pas
      {"t": "2026-06-29", "v": 101_000.0}]


def test_la_reference_est_replacee_sur_le_CAPITAL_de_depart():
    """En dollars, pas en base 100 : la courbe répond à « où en serais-je si j'avais mis
    la même somme ailleurs », et l'écart entre deux courbes est un nombre de dollars."""
    dates = ["2026-06-22", "2026-06-26", "2026-06-29"]
    closes = [400.0, 420.0, 410.0]                      # +5 % puis +2,5 % vs départ

    s = aligner(PF, dates, closes)
    assert s[0] == {"t": "2026-06-22", "v": 100_000.0}  # même point de départ que le PF
    assert s[2]["v"] == 102_500.0                       # 100 000 × 410/400


def test_un_point_du_WEEK_END_prend_la_derniere_cloture_CONNUE():
    """LA règle qui protège la mesure. Le portefeuille est valorisé le samedi ; l'action
    ne cote pas. Prendre la clôture du LUNDI ferait entrer dans la comparaison une
    information que le samedi n'avait pas — un look-ahead systématique, qui flatterait
    toujours la référence la plus volatile."""
    dates = ["2026-06-22", "2026-06-26", "2026-06-29"]
    closes = [400.0, 420.0, 999.0]                      # 999 = le lundi, très haut

    samedi = aligner(PF, dates, closes)[1]
    assert samedi["t"] == "2026-06-27"
    assert samedi["v"] == 105_000.0            # 420 (vendredi), PAS 999 (lundi)


def test_une_reference_qui_commence_APRES_le_portefeuille_est_ECARTEE():
    """Mieux vaut une courbe absente qu'une courbe qui démarre sur une valeur supposée.
    La prolonger vers l'arrière afficherait une performance jamais observée."""
    assert aligner(PF, ["2026-06-25", "2026-06-29"], [400.0, 410.0]) == []

    r = comparaison(PF, {"Tardif": (["2026-06-25"], [400.0]),
                         "Complet": (["2026-06-20", "2026-06-29"], [400.0, 440.0])})
    assert list(r["benchmarks"]) == ["Complet"]
    assert r["ecartees"] == ["Tardif"]


def test_l_equity_totale_somme_les_comptes_par_date():
    par_broker = {"alpaca": [{"t": "2026-06-22", "v": 99_000.0},
                             {"t": "2026-06-23", "v": 99_500.0}],
                  "bitmart": [{"t": "2026-06-22", "v": 1_000.0}]}
    assert serie_totale(par_broker) == [{"t": "2026-06-22", "v": 100_000.0},
                                        {"t": "2026-06-23", "v": 99_500.0}]


def test_une_date_sans_second_compte_reste_publiee():
    """L'exclure creuserait un trou là où il y a une mesure ; la lisser inventerait la
    valeur du compte absent. On publie ce qu'on a, et seulement ça."""
    r = serie_totale({"a": [{"t": "2026-06-23", "v": 5.0}], "b": []})
    assert r == [{"t": "2026-06-23", "v": 5.0}]


def test_la_performance_se_lit_en_dollars_ET_en_pourcentage():
    p = performance(PF)
    assert p["debut"] == 100_000.0 and p["fin"] == 101_000.0
    assert p["variation"] == 1_000.0
    assert abs(p["variation_pct"] - 0.01) < 1e-9
    assert p["du"] == "2026-06-22" and p["au"] == "2026-06-29"


def test_series_vides_ne_font_rien_planter():
    assert aligner([], ["2026-06-22"], [400.0]) == []
    assert aligner(PF, [], []) == []
    assert performance([]) == {}
    assert serie_totale({}) == []
    assert comparaison([], {"S&P 500": (["2026-06-22"], [400.0])})["benchmarks"] == {}


def test_les_dates_et_cloture_desalignees_sont_refusees():
    """Un appelant qui passe 3 dates et 2 clôtures a un bug ; l'aligner sur la plus
    courte le masquerait et produirait une courbe fausse mais plausible."""
    assert aligner(PF, ["2026-06-22", "2026-06-26", "2026-06-29"], [400.0, 420.0]) == []
