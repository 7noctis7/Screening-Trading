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
    tronque = preset_backtest(d, top_k=30, panel_couverture=1.0)
    complet = preset_backtest(d, top_k=30)
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
