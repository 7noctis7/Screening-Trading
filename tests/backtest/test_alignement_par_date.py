"""Alignement PAR DATE — le préalable au biais du survivant.

`fenetre_commune` corrige la profondeur du panel mais garde l'empilement POSITIONNEL : on prend
les `L` dernières barres de chaque série et on les superpose. Cela suppose que toutes se
terminent le même jour. Vrai entre titres cotés, **faux par construction pour un délisté** dont
la dernière barre est sa radiation — ses prix de 2020 se retrouveraient collés sur les dates de
2026.

La propriété qui rend la migration sûre est testée en premier : sur un calendrier uniforme,
l'alignement par date doit produire des chiffres IDENTIQUES à l'alignement positionnel. Les
résultats ne bougent donc QUE là où le positionnel était faux.
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np

from packages.backtest.panel import aligner_par_date, dernier_connu
from packages.backtest.preset_backtest import preset_backtest


@dataclass
class Bar:
    ts: datetime
    close: float


def _serie(n: int, seed: int, fin: datetime | None = None) -> list[Bar]:
    import random
    rng = random.Random(seed)
    fin = fin or datetime(2026, 1, 1, tzinfo=timezone.utc)
    debut = fin - timedelta(days=n - 1)
    px, out = 100.0, []
    for i in range(n):
        px *= math.exp(0.08 / 252 + 0.20 / math.sqrt(252) * rng.gauss(0, 1))
        out.append(Bar(debut + timedelta(days=i), px))
    return out


def _uniforme(n=40, longueur=1200):
    return {f"S{i}": _serie(longueur, i) for i in range(n)}


# --- LA PROPRIÉTÉ DE SÉCURITÉ ----------------------------------------------------------------

def test_calendrier_uniforme_donne_EXACTEMENT_les_memes_chiffres():
    """Sans cette égalité, activer l'alignement par date changerait des résultats sans qu'on
    puisse dire lesquels étaient faux."""
    d = _uniforme()
    a = preset_backtest(d, top_k=20, aligner_dates=False)
    b = preset_backtest(d, top_k=20, aligner_dates=True)
    assert a["curves"]["preset"] == b["curves"]["preset"]
    for cle in ("annualized", "sharpe", "max_drawdown", "total_return"):
        assert a["preset"][cle] == b["preset"][cle]


def test_la_matrice_alignee_egale_l_empilement_positionnel():
    d = _uniforme(n=10, longueur=300)
    noms, dates, A, _ = aligner_par_date(d, list(d))
    B = np.asarray([[b.close for b in d[s]] for s in noms])
    assert A.shape == B.shape and np.allclose(A, B)
    assert len(dates) == 300


def test_l_alignement_par_date_est_desactive_par_defaut():
    """Les chiffres publiés ne doivent pas bouger tant que le levier n'a pas été MESURÉ sur
    données réelles — c'est la discipline du dépôt, pas une timidité."""
    d = _uniforme(n=20, longueur=600)
    defaut = preset_backtest(d, top_k=10)
    explicite = preset_backtest(d, top_k=10, aligner_dates=False)
    assert defaut["curves"]["preset"] == explicite["curves"]["preset"]


# --- CE QUE L'ALIGNEMENT PAR DATE CHANGE, ET POURQUOI C'EST VOULU -----------------------------

def test_un_titre_introduit_tard_est_GARDÉ_avec_des_NaN():
    """L'empilement positionnel devait choisir : écarter le titre, ou tronquer tout le panel.
    L'alignement par date ne choisit pas — le titre entre quand il est coté."""
    d = _uniforme(n=20, longueur=1200)
    d["IPO"] = _serie(200, 999)                      # même fin, historique court
    noms, dates, A, diag = aligner_par_date(d, list(d), couverture=0.8)
    assert "IPO" in noms and diag["n_partielles"] == 1
    i = noms.index("IPO")
    assert not np.isfinite(A[i, 0])                   # pas coté au début
    assert np.isfinite(A[i, -1])                      # coté à la fin
    assert np.isfinite(A[i]).sum() == 200


def test_un_delisté_a_des_NaN_APRÈS_sa_radiation_jamais_des_zeros():
    """Écrire zéro produirait un rendement de −100 % le jour de la radiation, puis une série
    plate à zéro : une perte inventée, puis un actif fantôme."""
    d = _uniforme(n=20, longueur=1200)
    d["MORT"] = _serie(900, 777, fin=datetime(2024, 6, 1, tzinfo=timezone.utc))
    noms, dates, A, _ = aligner_par_date(d, list(d), couverture=0.5)
    i = noms.index("MORT")
    fini = np.isfinite(A[i])
    assert fini.any() and not fini[-1]                # coté au début de la fenêtre, plus à la fin
    assert not (A[i][~fini] == 0).any()               # jamais 0 — NaN


def test_un_delisté_peut_entrer_dans_l_univers():
    """Le cœur du P0-2 : sans ça, le test de biais du survivant ne mesure rien."""
    surv = {f"S{i}": _serie(1200, i) for i in range(30)}
    mort = {f"D{i}": _serie(900, 500 + i, fin=datetime(2024, 6, 1, tzinfo=timezone.utc))
            for i in range(5)}
    r = preset_backtest({**surv, **mort}, top_k=20, aligner_dates=True, panel_couverture=0.5)
    assert r["available"]
    assert [s for s in r["univers"] if s in mort], "aucun délisté sélectionné"


# --- VALORISATION D'UNE LIGNE QUI CESSE DE COTER ----------------------------------------------

def test_dernier_connu_reporte_le_passé_jamais_le_futur():
    A = np.array([[1.0, 2.0, 3.0, 4.0], [1.0, 2.0, np.nan, np.nan], [np.nan] * 4])
    # NaN != NaN : on compare donc les valeurs finies séparément de la finitude.
    v1 = dernier_connu(A, 1)
    assert v1[0] == 2.0 and v1[1] == 2.0 and not np.isfinite(v1[2])
    assert dernier_connu(A, 3)[1] == 2.0              # report du dernier cours connu
    assert not np.isfinite(dernier_connu(A, 3)[2])    # jamais cotée → reste inconnue
    assert dernier_connu(A, 0)[0] == 1.0              # aucun report depuis le futur


def test_dernier_connu_est_neutre_sur_une_matrice_complete():
    A = np.arange(12.0).reshape(3, 4)
    for t in range(4):
        assert np.allclose(dernier_connu(A, t), A[:, t])


def test_une_ligne_radiée_ne_contamine_pas_le_pas():
    """Un NaN dans le rendement d'une seule ligne rendrait NaN le rendement du portefeuille."""
    surv = {f"S{i}": _serie(1200, i) for i in range(30)}
    mort = {"D": _serie(900, 999, fin=datetime(2024, 6, 1, tzinfo=timezone.utc))}
    r = preset_backtest({**surv, **mort}, top_k=20, aligner_dates=True, panel_couverture=0.5)
    assert r["available"]
    assert all(math.isfinite(x) for x in r["curves"]["preset"])
    assert math.isfinite(r["preset"]["sharpe"])


# --- ROBUSTESSE ------------------------------------------------------------------------------

def test_panel_vide_ou_trop_petit_ne_leve_pas():
    noms, dates, A, diag = aligner_par_date({}, [])
    assert noms == [] and dates == [] and diag["available"] is False
    d = {"A": _serie(10, 1)}
    _, _, _, diag2 = aligner_par_date(d, ["A"], min_noms=5)
    assert diag2["available"] is False


def test_les_seances_horodatees_differemment_sont_la_meme_date():
    """Deux sources peuvent clôturer la même séance à des heures différentes : comparer les
    instants créerait deux dates pour une seule séance."""
    j = datetime(2026, 1, 5, tzinfo=timezone.utc)
    d = {"A": [Bar(j.replace(hour=21), 10.0)], "B": [Bar(j.replace(hour=16), 20.0)],
         "C": [Bar(j.replace(hour=9), 30.0)], "D": [Bar(j.replace(hour=1), 40.0)],
         "E": [Bar(j.replace(hour=23), 50.0)]}
    noms, dates, A, _ = aligner_par_date(d, list(d), min_noms=5)
    assert dates == ["2026-01-05"] and A.shape == (5, 1) and np.isfinite(A).all()


# --- EXÉCUTION RÉALISTE PAR DÉFAUT ------------------------------------------------------------

def test_l_execution_est_decalee_d_une_barre_par_defaut():
    """`exec_lag=0` remplissait au close de la barre de SIGNAL — un cours non exécutable au
    moment de la décision, que le dépôt documentait lui-même comme un mini look-ahead.

    Mesuré sur données réelles une fois l'alignement en place, `exec_lag=1` est meilleur sur
    TOUTES les colonnes (Sharpe, Sortino, maxDD, à turnover égal). Le gate du labo l'avait
    rejeté car il exige +0,05 de Sharpe : il demande « ce levier apporte-t-il de la valeur ? ».
    Mauvaise question — on ne garde pas un biais connu au motif que le retirer ne rapporte pas
    assez."""
    import inspect

    from packages.backtest.preset_backtest import EXEC_LAG_PAR_DEFAUT, preset_backtest

    assert EXEC_LAG_PAR_DEFAUT == 1
    assert inspect.signature(preset_backtest).parameters["exec_lag"].default == 1


def test_l_ancien_fill_reste_reproductible():
    """On doit pouvoir refaire tourner l'ancien comportement pour comparer — sinon l'écart
    n'est plus vérifiable et le chiffre publié devient un acte de foi."""
    d = _uniforme(n=20, longueur=800)
    ancien = preset_backtest(d, top_k=10, exec_lag=0)
    nouveau = preset_backtest(d, top_k=10)
    assert ancien["available"] and nouveau["available"]
    assert ancien["curves"]["preset"] != nouveau["curves"]["preset"]
