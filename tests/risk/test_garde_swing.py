"""Régime de marché et plafond de corrélation : les deux garde-fous qui REFUSENT.

Un garde-fou dont on ne teste que le cas passant ne garde rien. Chaque règle est donc
testée sur son cas de refus, et sur la façon dont elle se comporte quand la donnée
manque — c'est là que les filtres se contournent tout seuls.
"""

from packages.risk.garde_swing import (
    _correlation,
    exposition_autorisee,
    filtrer_correlation,
    grappes_correlees,
    regime_marche,
)


def _tendance(n: int, depart: float, pente: float) -> list[float]:
    return [depart + pente * i for i in range(n)]


def test_regime_bear_sous_la_moyenne_200_reduit_de_moitie():
    closes = _tendance(250, 300.0, -0.5)           # baisse régulière : dernier < MM200
    r = regime_marche(closes)
    assert r["regime"] == "bear" and r["facteur_long"] == 0.5


def test_regime_bull_au_dessus_de_la_moyenne_200_n_impose_rien():
    r = regime_marche(_tendance(250, 100.0, 0.5))
    assert r["regime"] == "bull" and r["facteur_long"] == 1.0


def test_historique_trop_court_n_invente_pas_un_regime():
    """Sans 200 clôtures il n'y a pas de MM200. On le dit, et on ne réduit rien."""
    r = regime_marche(_tendance(50, 100.0, 1.0))
    assert r["disponible"] is False and r["facteur_long"] == 1.0
    assert "indéterminé" in r["motif"]


def test_correlation_refuse_des_longueurs_differentes():
    """Recadrer en silence sur `[-m:]` est l'origine de trois bugs d'empilement ici."""
    assert _correlation([0.01] * 40, [0.01] * 30) is None


def test_grappes_par_liaison_simple():
    """A~B et B~C : les trois comptent comme un seul risque, même si A et C diffèrent."""
    base = [0.01 * (-1) ** i for i in range(60)]
    grappes = grappes_correlees({
        "A": base,
        "B": [x * 1.02 for x in base],             # quasi identique à A
        "C": [x * 0.98 for x in base],             # quasi identique à B
        "D": [0.01 * (-1) ** (i // 7) for i in range(60)],   # autre rythme
    })
    assert len(grappes) == 1
    assert set(grappes[0]) == {"A", "B", "C"}


def _closes(rends: list[float], base: float = 100.0) -> list[float]:
    out = [base]
    for r in rends:
        out.append(out[-1] * (1 + r))
    return out


def test_au_plus_trois_lignes_par_grappe_et_l_ordre_fait_foi():
    """L'ordre des candidats EST l'ordre de priorité : ce module coupe, il ne classe pas."""
    base = [0.012 * (-1) ** i + 0.0005 * i for i in range(40)]
    closes = {n: _closes([x * f for x in base])
              for n, f in (("A", 1.0), ("B", 1.01), ("C", 0.99), ("D", 1.02))}
    r = filtrer_correlation(["A", "B", "C", "D"], closes, fenetre=30, maximum=3)
    assert r["retenus"] == ["A", "B", "C"]
    assert [x["symbole"] for x in r["refuses"]] == ["D"]
    # ordre inversé : c'est A qui saute, pas D
    r2 = filtrer_correlation(["D", "C", "B", "A"], closes, fenetre=30, maximum=3)
    assert r2["retenus"] == ["D", "C", "B"]


def test_un_titre_a_historique_trop_court_est_refuse_pas_laisse_passer():
    """Sinon il suffirait d'une introduction récente pour contourner le plafond."""
    base = [0.012 * (-1) ** i + 0.0005 * i for i in range(40)]
    closes = {n: _closes([x * f for x in base])
              for n, f in (("A", 1.0), ("B", 1.01), ("C", 0.99), ("D", 1.02))}
    closes["NEUF"] = _closes(base[:5])             # 5 barres seulement
    r = filtrer_correlation(["A", "B", "C", "D", "NEUF"], closes, fenetre=30, maximum=3)
    assert "NEUF" not in r["retenus"]
    assert "NEUF" in r["sans_donnees"]
    motifs = {x["symbole"]: x["motif"] for x in r["refuses"]}
    assert "non mesurable" in motifs["NEUF"]


def test_les_deux_gardes_se_composent_sans_se_confondre():
    """Le régime module la TAILLE, la corrélation coupe des LIGNES — deux choses."""
    base = [0.012 * (-1) ** i + 0.0005 * i for i in range(40)]
    closes = {n: _closes([x * f for x in base])
              for n, f in (("A", 1.0), ("B", 1.01), ("C", 0.99), ("D", 1.02))}
    r = exposition_autorisee(_tendance(250, 300.0, -0.5), ["A", "B", "C", "D"],
                             closes, fenetre=30, maximum=3)
    assert r["facteur_long"] == 0.5                # bear
    assert r["retenus"] == ["A", "B", "C"]         # et D coupé pour corrélation
