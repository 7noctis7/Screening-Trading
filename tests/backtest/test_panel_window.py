"""Fenêtre commune du panel + compteurs de déclenchement.

Régression du 24/08 : sur 929 titres et dix ans en base, le preset ne produisait que
7 rebalancements — une seule introduction récente tronquait tout le panel via `min(len)`.
Conséquence : les leviers de risque ne pouvaient PAS se déclencher (l'overlay exige
`len(port) >= 10`), et le labo les imprimait « rejetés » comme s'ils avaient été testés.
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from packages.backtest.panel import fenetre_commune, rebalancements
from packages.backtest.preset_backtest import preset_backtest


@dataclass
class Bar:
    ts: datetime
    close: float


def _serie(n: int, seed: int) -> list[Bar]:
    import random
    rng = random.Random(seed)
    px, out, t0 = 100.0, [], datetime(2015, 1, 1, tzinfo=timezone.utc)
    for i in range(n):
        px *= math.exp(0.08 / 252 + 0.20 / math.sqrt(252) * rng.gauss(0, 1))
        out.append(Bar(t0 + timedelta(days=i), px))
    return out


def _panel_avec_ipo(n_longs=40, n_courts=6, long=1200, court=267):
    d = {f"S{i}": _serie(long, i) for i in range(n_longs)}
    d.update({f"IPO{i}": _serie(court, 900 + i) for i in range(n_courts)})
    return d


def test_une_serie_courte_ne_tronque_plus_le_panel():
    d = _panel_avec_ipo()
    _, L_min, _ = fenetre_commune(d, list(d), couverture=1.0)     # ancien comportement
    retenus, L, diag = fenetre_commune(d, list(d), couverture=0.8)
    assert L_min == 267                                           # la plus courte dictait tout
    assert L == 1200 and len(retenus) == 40
    assert diag["n_ecartes"] == 6 and diag["gain_vs_min"] > 4


def test_couverture_1_reproduit_exactement_min():
    d = _panel_avec_ipo()
    _, L, _ = fenetre_commune(d, list(d), couverture=1.0)
    assert L == min(len(v) for v in d.values())


def test_min_noms_respecte_meme_si_couverture_absurde():
    """Une couverture de 0 ne doit pas réduire le panel à un seul titre."""
    d = _panel_avec_ipo()
    retenus, _, _ = fenetre_commune(d, list(d), couverture=0.0, min_noms=5)
    assert len(retenus) >= 5


def test_panel_vide_ne_leve_pas():
    retenus, L, diag = fenetre_commune({}, [])
    assert retenus == [] and L == 0 and diag["available"] is False


def test_rebalancements_compte_les_pas_reels():
    assert rebalancements(267, 120, 21) == 7
    assert rebalancements(1200, 120, 21) > 20
    assert rebalancements(50, 120, 21) == 0


def test_preset_gagne_des_rebalancements():
    d = _panel_avec_ipo()
    # Ce test porte sur la fenêtre COMMUNE (empilement positionnel) : depuis l'activation de
    # l'alignement par date, il faut épingler ce mode, sinon on teste autre chose.
    tronque = preset_backtest(d, top_k=30, panel_couverture=1.0, aligner_dates=False)
    complet = preset_backtest(d, top_k=30, aligner_dates=False)
    assert tronque["n_steps"] < 10                       # le bug tel qu'il se manifestait
    assert complet["n_steps"] > 4 * tronque["n_steps"]
    assert complet["panel"]["n_ecartes"] == 6


def test_compteurs_distinguent_desactive_et_jamais_declenche():
    d = _panel_avec_ipo()
    sans = preset_backtest(d, top_k=30)
    avec = preset_backtest(d, top_k=30, max_weight=0.10, corr_tighten=True, risk_overlay=True)
    # garde-fou désactivé → clé ABSENTE (pas un zéro qui crierait au loup)
    assert "plafond" not in sans["declenchements"]
    assert "taper_dd" not in sans["declenchements"]
    # garde-fou actif → clé présente, valeur = nombre de pas où il a mordu
    for k in ("plafond", "taper_dd", "frein_vol"):
        assert k in avec["declenchements"]
    assert avec["declenchements"]["regime"] >= 0
    # les gardes toujours actifs sont toujours comptés
    assert {"blackout", "vol_target", "bande"} <= set(sans["declenchements"])


def test_compteur_plafond_mord_quand_le_cap_est_serre():
    d = _panel_avec_ipo()
    serre = preset_backtest(d, top_k=30, max_weight=0.02)     # 30 noms → 1/30 > 2 % impossible
    assert serre["declenchements"]["plafond"] > 0


# --- MIGRATION DES 13 SITES RESTANTS (P0-1) --------------------------------------------------

def test_les_poids_de_PRODUCTION_ignorent_une_serie_courte():
    """LE test qui a démenti mon raisonnement.

    Je pensais `preset_latest_weights` à l'abri : tout y est ancré sur la FIN (`[-L:]`,
    `t = L-1`), donc une troncature semblait inoffensive. Mesure : une seule série de 125 barres,
    incapable d'entrer dans le top-12 par qualité, déplaçait les poids envoyés au courtier de
    2 points. Cause : `_regime_mult` lit `hist[-200:]` et le PIC historique de l'indice — sur un
    panel tronqué la « MM200 » devient une MM125 et le pic ignore tout ce qui précède.
    """
    from packages.backtest.preset_backtest import preset_latest_weights

    base = {f"S{i}": _serie(2500, i) for i in range(40)}
    q = {s: float(i) for i, s in enumerate(base)}
    avant = preset_latest_weights(base, q, top_k=12)
    assert avant, "l'allocation de référence ne doit pas être vide"

    avec_ipo = dict(base, IPO=_serie(125, 999))
    q_ipo = dict(q, IPO=-1.0)                     # qualité minimale → jamais dans le top-12
    apres = preset_latest_weights(avec_ipo, q_ipo, top_k=12)

    assert set(avant) == set(apres)
    for k in set(avant) | set(apres):
        assert abs(avant.get(k, 0.0) - apres.get(k, 0.0)) < 1e-9


def test_l_eligibilite_exige_de_quoi_calculer_une_MM200():
    """Un univers dont AUCUNE série n'atteint 200 barres ne peut pas produire de poids :
    la porte de régime serait calculée sur une moyenne qui n'est pas celle qu'elle annonce."""
    from packages.backtest.preset_backtest import MIN_BARRES_REGIME, preset_latest_weights

    assert MIN_BARRES_REGIME == 200
    court = {f"S{i}": _serie(180, i) for i in range(20)}
    assert preset_latest_weights(court, {s: 1.0 for s in court}) == {}


def test_fenetre_par_rang_garde_les_plus_anciens():
    """Profondeur par RANG : 12 séries longues l'emportent sur 18 séries courtes — c'est le
    compromis inverse de `fenetre_commune`, et il est délibéré (courbe du tableau de bord)."""
    from packages.backtest.panel import fenetre_par_rang

    d = {f"L{i}": [0] * 2500 for i in range(12)}
    d.update({f"C{i}": [0] * 300 for i in range(18)})
    retenus, L = fenetre_par_rang(d, list(d), min_noms=12)
    assert L == 2500 and len(retenus) == 12
    # la même donnée par COUVERTURE privilégie la largeur : plus de noms, moins de profondeur
    _, L_couv, _ = fenetre_commune(d, list(d), couverture=0.8)
    assert L_couv < L


def test_fenetre_par_rang_ne_vide_jamais_le_panel():
    from packages.backtest.panel import fenetre_par_rang

    assert fenetre_par_rang({}, [], min_noms=12) == ([], 0)
    d = {"A": [0] * 100}
    assert fenetre_par_rang(d, ["A"], min_noms=99) == (["A"], 100)


def test_tous_les_backtests_publient_leur_profondeur():
    """Un ratio annualisé sans le nombre de pas qui l'a produit n'est pas contestable."""
    from packages.backtest.conviction_backtest import conviction_backtest
    from packages.backtest.megacap import megacap_rotation
    from packages.backtest.weighting_backtest import weighting_backtest

    d = _panel_avec_ipo(n_longs=40, long=1200)
    for nom, res in [("conviction", conviction_backtest(d, top_n=10)),
                     ("megacap", megacap_rotation(d, top_n=10)),
                     ("weighting", weighting_backtest(d, max_assets=40))]:
        if res.get("available"):
            assert res.get("panel", {}).get("available"), f"{nom} ne publie pas sa profondeur"
            assert res["panel"]["n_ecartes"] >= 0
