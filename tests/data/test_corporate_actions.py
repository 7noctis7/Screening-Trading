"""Le garde-fou ne protégeait que d'un côté — et corriger sans preuve serait pire.

Le seuil de 150 % attrapait les regroupements (+900 %) et laissait passer les splits (−75 %),
c'est-à-dire le cas fréquent, sur les valeurs qui montent. Mais ajuster un VRAI krach
transformerait une perte réelle en rendement inventé : ces tests figent les deux exigences.
"""
from packages.data.corporate_actions import ajuster, detecter, exploitable


def _serie(n=40, p0=100.0, pas=1.0):
    return [p0 + i * pas for i in range(n)]


def _vols(n=40, v=1_000_000.0):
    return [v] * n


# --- ce que l'ancien filtre laissait passer ---------------------------------------------------

def test_un_split_4_pour_1_est_detecte():
    """-75 % : sous le seuil de 150 %, donc invisible pour l'ancien garde-fou."""
    c = _serie(20) + [v / 4 for v in _serie(20, p0=120.0)]
    v = _vols(20) + [x * 4 for x in _vols(20)]
    cands = detecter(c, v)
    assert len(cands) == 1
    assert cands[0].certain
    assert abs(cands[0].ratio_usuel - 0.25) < 1e-9


def test_le_split_est_retropropage_et_la_serie_devient_continue():
    avant = _serie(20)
    apres = [v / 4 for v in _serie(20, p0=120.0)]
    v = _vols(20) + [x * 4 for x in _vols(20)]
    ajustes, _ = ajuster(avant + apres, v)
    r = [ajustes[i + 1] / ajustes[i] - 1 for i in range(len(ajustes) - 1)]
    assert max(abs(x) for x in r) < 0.10, "un saut subsiste : la série n'est pas continue"


def test_un_split_2_pour_1_aussi():
    c = _serie(20) + [v / 2 for v in _serie(20, p0=120.0)]
    v = _vols(20) + [x * 2 for x in _vols(20)]
    assert detecter(c, v)[0].certain


# --- ce qu'il ne faut SURTOUT pas ajuster -----------------------------------------------------

def test_un_vrai_krach_nest_pas_pris_pour_un_split():
    """-38 % de marché : ratio quelconque, aucune fraction simple. On n'y touche pas."""
    c = _serie(20) + [v * 0.62 for v in _serie(20, p0=120.0)]
    assert detecter(c, _vols(40)) == []
    ajustes, _ = ajuster(c, _vols(40))
    assert ajustes == c, "la série a été modifiée alors qu'il s'agit d'un mouvement de marché"


def test_un_krach_pile_sur_une_fraction_simple_nest_pas_ajuste_sans_le_volume():
    """-50 % pile, mais volume inchangé : le doute existe, donc on ne tranche pas."""
    c = _serie(20) + [v * 0.5 for v in _serie(20, p0=120.0)]
    cands = detecter(c, _vols(40))
    assert len(cands) == 1 and not cands[0].certain
    ajustes, _ = ajuster(c, _vols(40))
    assert ajustes == c, "un candidat non confirmé ne doit jamais être appliqué"


def test_sans_volume_on_ne_tranche_jamais():
    c = _serie(20) + [v / 4 for v in _serie(20, p0=120.0)]
    cands = detecter(c, None)
    assert len(cands) == 1 and not cands[0].certain
    assert "non tranché" in exploitable(c, None)[1]


def test_serie_saine_est_exploitable():
    ok, motif = exploitable(_serie(60), _vols(60))
    assert ok and motif == ""


def test_une_serie_a_doute_est_declaree_inexploitable():
    """Mieux vaut un titre écarté qu'un rendement inventé au milieu de l'historique."""
    c = _serie(20) + [v * 0.5 for v in _serie(20, p0=120.0)]
    ok, motif = exploitable(c, _vols(40))
    assert not ok and "split non tranché" in motif


def test_le_split_confirme_rend_la_serie_exploitable():
    c = _serie(20) + [v / 4 for v in _serie(20, p0=120.0)]
    v = _vols(20) + [x * 4 for x in _vols(20)]
    assert exploitable(c, v)[0]


# --- robustesse ------------------------------------------------------------------------------

def test_series_degenerees_ne_plantent_pas():
    assert detecter([], None) == []
    assert detecter([100.0], None) == []
    assert detecter([100.0, 0.0, 50.0], None) == []      # prix nul ignoré, pas d'exception


def test_petites_variations_ignorees():
    """On ne cherche même pas un split sous 30 % : le marché bouge."""
    c = [100.0, 90.0, 100.0, 88.0] + _serie(20)
    assert detecter(c, _vols(24)) == []
