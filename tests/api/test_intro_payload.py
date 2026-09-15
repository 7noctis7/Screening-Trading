"""Les chiffres de l'intro sont DÉRIVÉS. Aucun n'est saisi, aucun n'est deviné.

CE QUE CES TESTS PROTÈGENT. La landing affichait « −9 % » de drawdown, issu d'un run
`backtest-preset` du 23/06 sur le PRESET SEUL et une fenêtre courte — son indice de
comparaison y montre 180 % de CAGR — pas un chiffre décennal. Le même dépôt
enregistre, pour l'allocation de PRODUCTION sur 2016→2026, un maxDD de −25,3 %.

Les deux sont vrais. Ils ne décrivent pas la même chose, et rien à l'écran ne le disait.
Un nombre recopié dans un composant se détache de ce qu'il mesure — d'autant plus vite
comparaison y montre 180 % de CAGR — pas un chiffre décennal. Le dépôt enregistre,
lui, un maxDD de −25,3 % pour l'allocation de PRODUCTION sur 2016→2026.
"""

from __future__ import annotations

from datetime import date, timedelta

from apps.api.intro_payload import MIN_POINTS_CAGR, construire, periode, trades

AUJ = date(2026, 9, 15)


def _serie(n: int, taux: float, fin: date = AUJ) -> list[dict]:
    """`n` points quotidiens finissant à `fin`, croissant de `taux` par point."""
    return [{"t": (fin - timedelta(days=n - 1 - i)).isoformat(),
             "v": 100 * (1 + taux) ** i} for i in range(n)]


# ── ce qui manque est DIT, jamais comblé ──────────────────────────────────────

def test_une_fenetre_sans_donnee_le_dit():
    p = periode(_serie(5, 0.001), "10a", "10 ANS", 10, AUJ)
    # Cinq points existent, donc la fenêtre est « disponible » — mais pas annualisable.
    assert p["disponible"] and p["cagr"] is None
    assert "trop courte" in p["cagr_motif"]


def test_une_courbe_vide_ne_produit_aucun_chiffre():
    p = periode([], "tout", "DEPUIS LE DÉBUT", None, AUJ)
    assert p["disponible"] is False and p["motif"]


def test_sans_trade_cloture_on_ne_calcule_pas_d_esperance():
    assert trades({"count": 0})["disponible"] is False
    assert trades({})["disponible"] is False


def test_une_perte_moyenne_nulle_rend_le_ratio_indefini_pas_infini():
    """Diviser par zéro produirait `inf`, que le front afficherait comme un chiffre."""
    t = trades({"count": 3, "avg_win": 10.0, "avg_loss": 0.0, "pnl_total": 30.0})
    assert t["ratio_gain_perte"] is None


# ── l'annualisation refuse les fenêtres courtes ───────────────────────────────

def test_trois_mois_de_hausse_ne_deviennent_pas_un_taux_annuel():
    """+20 % en trois mois annualisés feraient +107 % — aucune année ne fait ça."""
    p = periode(_serie(60, 0.003), "ytd", "YTD", 0, AUJ)
    assert p["croissance"] > 0.15
    assert p["cagr"] is None


def test_une_fenetre_assez_longue_annualise():
    """Deux conditions, et les deux comptent : assez de POINTS et assez d'ANNÉES.

    250 points quotidiens font 0,68 an — sous le seuil de 0,75. Il faut donc une série
    plus longue que `MIN_POINTS_CAGR` seul ne le laisse croire.
    """
    p = periode(_serie(400, 0.0005), "3a", "3 ANS", 3, AUJ)
    assert p["cagr"] is not None and 0 < p["cagr"] < 0.5
    assert p["annees"] >= 0.75


def test_assez_de_points_mais_pas_assez_d_annees_ne_suffit_pas():
    """Un pas horaire ferait 300 points en deux semaines : annualiser resterait faux."""
    dense = [{"t": (AUJ - timedelta(days=13 - i // 24)).isoformat(), "v": 100 + i}
             for i in range(MIN_POINTS_CAGR + 120)]
    assert periode(dense, "tout", "T", None, AUJ)["cagr"] is None


# ── le drawdown est un vrai pire-recul, pas un min ────────────────────────────

def test_le_drawdown_mesure_le_recul_DEPUIS_UN_SOMMET():
    courbe = [{"t": f"2026-01-{d:02d}", "v": v}
              for d, v in enumerate([100, 120, 90, 130], start=1)]
    p = periode(courbe, "tout", "T", None, AUJ)
    assert abs(p["max_drawdown"] - (90 / 120 - 1)) < 1e-9   # −25 %, pas −10 %


def test_une_courbe_qui_ne_recule_jamais_a_un_drawdown_nul():
    assert periode(_serie(40, 0.002), "tout", "T", None, AUJ)["max_drawdown"] == 0.0


# ── la comparaison part du MÊME jour ──────────────────────────────────────────

def test_les_deux_courbes_sont_en_base_100_au_meme_depart():
    nous, ref = _serie(300, 0.001), _serie(300, 0.0004)
    p = periode(nous, "tout", "T", None, AUJ, reference=ref)
    assert p["courbe"][0] == 100.0 and p["reference"][0] == 100.0
    assert p["courbe"][-1] > p["reference"][-1]      # la nôtre monte plus vite


def test_la_reference_est_tranchee_au_depart_REEL_de_notre_serie():
    """Si le backtest commence après l'indice, comparer depuis la borne théorique
    donnerait à l'indice une avance qu'il n'a pas eue face à nous."""
    nous = _serie(200, 0.001)                     # 200 jours seulement
    ref = _serie(900, 0.001)                      # l'indice remonte bien plus loin
    p = periode(nous, "3a", "3 ANS", 3, AUJ, reference=ref)
    assert len(p["reference"]) == len(p["courbe"])
    assert abs(p["reference_croissance"] - p["croissance"]) < 1e-6


def test_une_reference_absente_est_NOMMEE_pas_silencieuse():
    p = periode(_serie(50, 0.001), "tout", "T", None, AUJ, reference=None)
    assert p["reference"] is None and p["reference_motif"]


def test_le_reechantillonnage_garde_le_DERNIER_point():
    """C'est lui qui porte la performance finale : l'amputer fausserait la courbe."""
    p = periode(_serie(1000, 0.001), "tout", "T", None, AUJ)
    attendu = round(100 * (1.001 ** 999) / 100 * 100, 2)
    assert abs(p["courbe"][-1] - attendu) < 0.05


# ── la nature de la série est écrite, pas sous-entendue ───────────────────────

def test_le_payload_dit_que_c_est_un_BACKTEST():
    r = construire({"equity": _serie(50, 0.001)}, {"count": 0}, {"total": 929}, AUJ)
    assert "Backtest" in r["avertissement"]
    assert "paper" in r["avertissement"].lower()
    assert r["source"]


def test_les_cinq_fenetres_sont_toujours_rendues_meme_vides():
    """Une fenêtre absente doit apparaître avec son motif — sinon on croit qu'elle
    n'a jamais été demandée."""
    r = construire({"equity": _serie(10, 0.001)}, {"count": 0}, {"total": 929}, AUJ)
    assert [p["cle"] for p in r["periodes"]] == ["ytd", "3a", "5a", "10a", "tout"]
    assert all("libelle" in p for p in r["periodes"])


def test_une_exception_interne_ne_casse_pas_le_snapshot():
    r = construire({"equity": [{"t": "pas-une-date", "v": 10}]}, {}, {}, AUJ)
    assert r["periodes"][0]["disponible"] is False
