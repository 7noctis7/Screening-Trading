"""Audit de fuite du cœur momentum sectoriel — ce qui expliquait 55,5 % de CAGR.

Un CAGR de 55,5 % sur 9,4 ans avec un DSR de 100 % n'est pas un résultat, c'est une
alerte. L'audit du 04/09 a séparé trois causes, et il fallait les MESURER pour savoir
laquelle pèse :

  · coûts de transaction absents        → 0,64 point de CAGR (mesuré). Réel, mineur.
  · look-ahead dormant dans la MM50     → jamais lu aujourd'hui, mais réveillable.
  · univers de SURVIVANTS               → la cause principale, et elle est structurelle.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

import numpy as np

from packages.backtest.sector_momentum import (
    _biais_survivant,
    _sma,
    _turnover,
    sector_momentum_equity_daily,
)
from packages.core.models import Bar

SECTEURS = {"tech": 0.0006, "energie": 0.0001, "sante": 0.0003, "conso": 0.0002}


def _panneau(n: int = 900, par_secteur: int = 6, graine: int = 11):
    random.seed(graine)
    d0 = datetime(2020, 1, 6, tzinfo=UTC)
    data, sectors = {}, {}
    for sec, drift in SECTEURS.items():
        for j in range(par_secteur):
            sym = f"{sec[:3].upper()}{j}"
            sectors[sym] = sec
            v, bars = 100.0, []
            for i in range(n):
                v *= 1 + random.gauss(drift, 0.016)
                bars.append(Bar(sym, "1d", d0 + timedelta(days=i), v, v, v, v, 1e6))
            data[sym] = bars
    return data, sectors


# ───────────────────────────── coûts de transaction ─────────────────────────────

def test_la_rotation_COUTE_desormais_quelque_chose():
    """Ce cœur tourne mensuellement sur deux secteurs entiers et était comparé à QQQ,
    un buy-and-hold de turnover nul. Comparer une rotation gratuite à une détention
    gratuite avantage mécaniquement la rotation."""
    data, sectors = _panneau()
    sans = sector_momentum_equity_daily(data, sectors, cout_bps=0.0)
    avec = sector_momentum_equity_daily(data, sectors, cout_bps=5.0)
    assert sans["available"] and avec["available"]
    assert avec["equity"][-1] < sans["equity"][-1]
    assert avec["frais_cumules"] > 0
    assert sans["frais_cumules"] == 0.0


def test_les_frais_sont_PUBLIES_avec_le_resultat():
    """Un backtest qui tait ce qu'il a payé ne se compare pas à un autre."""
    res = sector_momentum_equity_daily(*_panneau())
    assert res["cout_bps"] == 5.0
    assert "frais_cumules" in res


def test_le_turnover_compte_les_deux_jambes():
    """Une rotation complète vend tout et rachète tout : 2,0, pas 1,0."""
    assert _turnover(["A", "B"], ["C", "D"]) == 2.0
    assert _turnover(["A", "B"], ["A", "B"]) == 0.0
    assert _turnover([], ["A", "B"]) == 1.0        # l'achat initial se paie aussi
    assert _turnover(["A", "B"], []) == 0.0        # rien à acheter : aucun panier cible


# ───────────────────────── le look-ahead dormant de la MM50 ─────────────────────

def test_le_prefixe_de_la_MM_ne_contient_plus_le_futur():
    """Les `w-1` premières cases recevaient `out[0]` — la moyenne des jours 0..w-1 —
    donc, lues à t=10, l'avenir. Jamais lues aujourd'hui (la boucle démarre à 126),
    mais un `lookback` plus court réveillerait la fuite en silence."""
    x = np.arange(1.0, 101.0)
    ma = _sma(x, 50)
    assert np.isnan(ma[:49]).all()                 # aucun préfixe fabriqué
    assert abs(ma[49] - x[:50].mean()) < 1e-9      # 1re valeur licite = moyenne 0..49
    assert abs(ma[99] - x[50:100].mean()) < 1e-9   # et elle reste GLISSANTE


def test_une_comparaison_avec_NaN_ecarte_le_titre_au_lieu_de_l_admettre():
    """C'est ce qui rend le NaN sûr : `cours > NaN` vaut False, donc le titre sort du
    filtre de tendance. L'inverse — l'admettre — serait une fuite silencieuse."""
    cours, mm = 100.0, float("nan")
    assert not (cours > mm)


# ─────────────────────────── le biais du survivant ───────────────────────────────

def test_un_univers_de_survivants_est_dit_ELEVE():
    """LA cause principale. Le nettoyage d'univers retire tout titre dont la dernière
    barre a plus de dix jours — donc tous les délistés, AVANT le backtest. Le classement
    sectoriel ne voit alors que les sociétés qui existent encore."""
    out = _biais_survivant(["AAPL", "MSFT", "NVDA"])
    assert out["available"] is True
    assert out["n_delistes_dans_le_panneau"] == 0
    assert out["severite"].startswith("ÉLEVÉ")


def test_des_delistes_PRESENTS_font_baisser_la_severite():
    """La mesure doit discriminer, sinon elle ne sert à rien."""
    from packages.data.survivorship import load_delisted
    catalogue = sorted({d["symbol"] for d in load_delisted()})
    out = _biais_survivant(["AAPL"] + catalogue[:3])
    assert out["n_delistes_dans_le_panneau"] == 3
    assert out["severite"].startswith("partiel")


def test_le_biais_VOYAGE_avec_le_resultat():
    """Un chiffre séparé de son biais se lit comme un résultat. C'est ce qui s'est
    produit : `survivorship_audit` savait répondre, mais n'était jamais attaché."""
    res = sector_momentum_equity_daily(*_panneau())
    assert "biais_survivant" in res
    assert res["biais_survivant"]["severite"].startswith("ÉLEVÉ")


def test_on_ne_compte_PAS_les_delistes_du_catalogue_absents_du_panneau():
    """`survivorship_audit` rapporte les délistés CONNUS au nombre d'actifs : avec 3
    titres vivants et 43 au catalogue il annonce « corrigé (partiel) » et 93,5 % de
    couverture. Il répond à « en connaît-on ? », pas à « sont-ils dans le panneau ? ».
    Un délisté absent ne corrige rien."""
    out = _biais_survivant(["AAPL", "MSFT", "NVDA"])
    assert out["n_catalogue"] > out["n_delistes_dans_le_panneau"]
    assert out["n_delistes_dans_le_panneau"] == 0
