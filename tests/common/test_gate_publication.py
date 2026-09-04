"""Le gate refuse l'IMPOSSIBLE, pas les mauvaises nouvelles.

Le 04/09, le site a publié — et le téléphone a affiché — gain total −100 %, CAGR −100 %,
pire baisse −100 %, avec un Sharpe de 0,25 et un Sortino de 0,18. Le gate de publication
était vert : fichiers présents, volumineux, datés du jour. Il ne regardait jamais les
nombres. C'est l'utilisateur qui l'a vu.
"""

from __future__ import annotations

from packages.common.gate_publication import (
    auditer,
    contradictions,
    trous_dans_courbe,
)

DEFAUT_04_09 = {"cagr": -1.0, "total_return": -1.0, "sharpe": 0.25,
                "sortino": 0.18, "max_drawdown": -1.0}


def test_le_cas_exact_du_04_09_est_refuse():
    """Un capital anéanti et un ratio positif sur la même série : impossible."""
    motifs = contradictions(DEFAUT_04_09)
    assert motifs
    assert any("sharpe" in m for m in motifs)
    assert any("sortino" in m for m in motifs)


def test_une_perte_SEVERE_mais_coherente_passe():
    """LE test qui garde le gate utile. Une stratégie a le droit de perdre beaucoup ; un
    gate qui refuse les mauvaises nouvelles finit par cacher les vraies."""
    assert contradictions({"cagr": -0.62, "total_return": -0.9, "sharpe": -1.4,
                           "sortino": -1.1, "max_drawdown": -0.71}) == []


def test_meme_un_aneantissement_COHERENT_passe():
    """Tout perdre est possible ; le faire avec un Sharpe positif ne l'est pas."""
    assert contradictions({"cagr": -1.0, "total_return": -1.0,
                           "sharpe": -2.3, "max_drawdown": -1.0}) == []


def test_une_equity_a_zero_qui_remonte_est_refusee():
    """Une equity qui touche zéro n'en revient pas : le produit est nul."""
    motifs = contradictions({"max_drawdown": -1.0, "total_return": 0.4})
    assert motifs and "ne remonte pas" in motifs[0]


def test_les_valeurs_absentes_ou_non_numeriques_ne_declenchent_rien():
    """Un bloc partiel n'est pas une incohérence : pas de cri sur du vide."""
    assert contradictions({}) == []
    assert contradictions(None) == []
    assert contradictions({"cagr": None, "sharpe": "n/d"}) == []
    assert contradictions({"cagr": float("nan"), "sharpe": 0.5}) == []


def test_un_booleen_n_est_pas_un_ratio():
    """`isinstance(True, int)` vaut True en Python : sans garde, un drapeau passerait
    pour un Sharpe de 1."""
    assert contradictions({"cagr": -1.0, "sharpe": True}) == []


# ─────────────────────────── les trous de courbe ───────────────────────────

def test_une_courbe_percee_est_detectee():
    """`_clean` convertit NaN en `null` pour garder le JSON valide — bon geste, mais le
    front lit le trou comme un zéro. C'est la CAUSE, pas seulement le symptôme."""
    assert trous_dans_courbe([100.0, None, 102.0]) == 1
    assert trous_dans_courbe([100.0, float("nan"), 102.0]) == 1
    assert trous_dans_courbe([100.0, "n/d", 102.0]) == 1


def test_une_courbe_saine_ou_absente_ne_declenche_rien():
    assert trous_dans_courbe([100.0, 101.0, 102.0]) == 0
    assert trous_dans_courbe([]) == 0
    assert trous_dans_courbe(None) == 0


# ─────────────────────────── l'audit récursif ───────────────────────────

def test_l_audit_trouve_les_blocs_IMBRIQUES():
    """Les stats et les courbes vivent à des profondeurs variables selon les pages ; une
    règle qui ne regarde qu'un chemin connu rate le prochain endroit où ça cassera."""
    motifs = auditer({"index_core": {"equity": [100.0, None]},
                      "perf": {"stats": DEFAUT_04_09}})
    assert any("/index_core/equity" in m for m in motifs)
    assert any("sharpe" in m for m in motifs)


def test_un_payload_sain_ne_produit_aucun_motif():
    assert auditer({"stats": {"cagr": 0.14, "sharpe": 0.95, "total_return": 2.1},
                    "index_core": {"equity": [100.0, 101.0, 102.0]}}) == []


def test_les_quatre_courbes_du_coeur_sont_surveillees():
    """preset, qqq, megacap, sector_mom — celle qui a cassé était `preset`."""
    for cle in ("preset", "qqq", "megacap", "sector_mom"):
        assert auditer({cle: [100.0, None]}), f"{cle} non surveillée"
