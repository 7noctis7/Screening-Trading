"""Le cœur sectoriel empilait POSITIONNELLEMENT — la troisième occurrence du même
défaut.

`fenetre_commune` prend les L dernières barres de chaque titre et les superpose, avec un
calendrier pris sur la SEULE série la plus longue. Un titre radié en 2018 versait donc
des
cours de 2018 dans des colonnes étiquetées 2026, et le classement de momentum comparait
des
rendements calculés sur des périodes calendaires DIFFÉRENTES au sein d'un même secteur.

Le preset avait été migré en #341, la production en #347. Ce cœur ne l'avait jamais été.
Mesuré sur la vraie base avant correction : 53,6 % de CAGR et 8908 % de rendement total
à
100 % de cœur — un résultat qui rendrait inutile tout le reste du système.
"""

import ast
import inspect
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import numpy as np

from packages.backtest import sector_momentum as sm


@dataclass
class Bar:
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


def _bars(px, debut=datetime(2015, 1, 1, tzinfo=UTC)):
    out, d = [], debut
    for v in px:
        while d.weekday() >= 5:
            d += timedelta(days=1)
        out.append(Bar(d, v, v, v, v, 1e6))
        d += timedelta(days=1)
    return out


# --------------------------------------------------------------------- _sma
def test_sma_tolere_un_trou():
    """LE piège de la migration : `np.cumsum` propage un NaN À L'INFINI. Un seul jour
    manquant rendrait la MM50 NaN pour tout le reste, le filtre `cours > MM50`
    deviendrait faux à jamais, et le titre serait exclu EN SILENCE."""
    x = np.array([10.0] * 60 + [np.nan] + [10.0] * 60)
    r = sm._sma(x, 50)
    assert not np.isnan(r[70:]).any(), "un trou contamine toute la suite de la MM"
    assert r[-1] == 10.0


def test_sma_divise_par_le_nombre_de_points_VALIDES():
    """Diviser par `w` au lieu du nombre de points disponibles sous-estimerait la
    moyenne dès qu'il manque une cotation — et le filtre de tendance laisserait
    passer des titres sous leur vraie moyenne."""
    x = np.array([np.nan] * 10 + [100.0] * 10)
    assert sm._sma(x, 5)[-1] == 100.0


def test_sma_serie_trop_courte_ne_rend_pas_NaN():
    assert sm._sma(np.array([np.nan, 10.0, 12.0]), 50)[0] == 11.0


# ------------------------------------------------------- verrou structurel
def test_le_coeur_sectoriel_aligne_PAR_DATE():
    """Verrou anti-re-dérive : on inspecte les IMPORTS effectifs, pas le texte — le nom
    de l'ancienne fonction reste cité dans le commentaire qui explique la migration."""
    arbre = ast.parse(inspect.getsource(sm))
    importes = {a.name for n in ast.walk(arbre)
                if isinstance(n, ast.ImportFrom) for a in n.names}
    assert "aligner_par_date" in importes
    assert "fenetre_commune" not in importes, "retour à l'empilement positionnel"


# --------------------------------------------------- le défaut, reproduit
def _panier():
    """Un secteur dont un membre est RADIÉ au milieu, après une envolée.

    Empilé positionnellement, son envolée de 2018 atterrit dans les colonnes RÉCENTES et
    rend le secteur artificiellement fort aujourd'hui. Aligné par date, il est absent de
    ces dates et n'entre pas dans le calcul — la seule lecture honnête.
    """
    n = 900
    data, secteurs = {}, {}
    for i in range(3):                                   # secteur CALME, série complète
        data[f"CALME{i}"] = _bars(list(np.linspace(100.0, 130.0, n)))
        secteurs[f"CALME{i}"] = "calme"
    for i in range(3):                                 # secteur PIEGE, complet
        data[f"PIEGE{i}"] = _bars(list(np.linspace(100.0, 108.0, n)))
        secteurs[f"PIEGE{i}"] = "piege"
    # le radié : x5 puis disparition à mi-parcours
    data["PIEGEZOMBIE"] = _bars(list(np.linspace(100.0, 500.0, n // 2)))
    secteurs["PIEGEZOMBIE"] = "piege"
    return data, secteurs


def test_un_titre_RADIE_ne_dope_pas_son_secteur_aujourd_hui():
    """Le test de fond. Le zombie s'arrête à mi-parcours ; ses cours ne doivent pas
    peser sur le momentum du secteur aux dates où il ne cote plus."""
    data, secteurs = _panier()
    r = sm.sector_momentum_equity_daily(data, secteurs, top_sectors=1, min_per_sector=2)
    assert r.get("available"), r
    assert "piege" not in (r.get("current_sectors") or []), (
        "le secteur du titre radié est retenu AUJOURD'HUI : ses cours d'avant la "
        f"radiation sont replacés dans les dates récentes — {r.get('current_sectors')}"
    )


def test_la_courbe_reste_exploitable():
    """Non-régression : la migration ne doit pas rendre le module inutilisable."""
    data, secteurs = _panier()
    r = sm.sector_momentum_equity_daily(data, secteurs, top_sectors=1, min_per_sector=2)
    assert r["available"] and len(r["equity"]) > 100
    assert all(np.isfinite(r["equity"])), "des NaN ont traversé jusqu'à la courbe"
