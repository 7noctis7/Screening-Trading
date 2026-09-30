"""Moteur long/flat : stops et cibles des stratégies du bot, sous les mêmes règles que SMCLXTP-A.

Les stratégies du registre (`ma_crossover`, `rsi_reversion`, `swing`) livrent avec leur
signal LONG un stop et une cible fixés au close du signal. Pour les comparer à SMCLXTP-A
(qui n'en a pas), le moteur les honore EN SÉANCE avec l'hypothèse défavorable : gap sous
le stop → ouverture ; stop et cible dans la même barre → le stop ; cible → au prix de la
cible, jamais mieux.
"""

from __future__ import annotations

import numpy as np
import pytest

from packages.backtest.signal_long_tp import simuler

N = 10


def _jours(n=N):
    return [f"2020-01-{k + 1:02d}" for k in range(n)]


def _niveaux(v, i):
    a = np.full(N, np.nan)
    a[i] = v
    return a


def _sig(*idx):
    s = np.zeros(N, bool)
    s[list(idx)] = True
    return s


def _cas(bas=None, hauts=None, ouvertures=None):
    o = np.full(N, 100.0) if ouvertures is None else np.asarray(ouvertures, float)
    c = np.full(N, 100.0)
    h = np.full(N, 101.0) if hauts is None else np.asarray(hauts, float)
    lo = np.full(N, 99.0) if bas is None else np.asarray(bas, float)
    return o, h, lo, c


def _run(o, h, lo, c, stop=95.0, cible=110.0, flat=()):
    return simuler(_jours(), o, c, _sig(1), _sig(*flat), debut=_jours()[0], cout=0.0,
                   haut=h, bas=lo, stops=_niveaux(stop, 1), cibles=_niveaux(cible, 1))


def test_stop_touche_en_seance():
    o, h, lo, c = _cas(bas=[99, 99, 99, 99, 94, 99, 99, 99, 99, 99])
    (t,) = _run(o, h, lo, c)["trades"]
    assert (t.sortie_jour, t.prix_sortie, t.motif_sortie) == ("2020-01-05", 95.0, "stop")


def test_gap_sous_le_stop_sort_a_l_ouverture():
    o, h, lo, c = _cas(bas=[99, 99, 99, 99, 88, 99, 99, 99, 99, 99],
                       ouvertures=[100, 100, 100, 100, 90, 100, 100, 100, 100, 100])
    (t,) = _run(o, h, lo, c)["trades"]
    assert t.prix_sortie == 90.0


def test_cible_au_prix_de_la_cible():
    o, h, lo, c = _cas(hauts=[101, 101, 101, 112, 101, 101, 101, 101, 101, 101])
    (t,) = _run(o, h, lo, c)["trades"]
    assert (t.prix_sortie, t.motif_sortie) == (110.0, "cible")


def test_stop_et_cible_la_meme_barre_le_stop():
    o, h, lo, c = _cas(bas=[99, 99, 99, 94, 99, 99, 99, 99, 99, 99],
                       hauts=[101, 101, 101, 112, 101, 101, 101, 101, 101, 101])
    assert _run(o, h, lo, c)["trades"][0].motif_sortie == "stop"


def test_le_stop_vaut_des_la_barre_d_entree():
    o, h, lo, c = _cas(bas=[99, 99, 94, 99, 99, 99, 99, 99, 99, 99])
    (t,) = _run(o, h, lo, c)["trades"]
    assert t.entree_jour == t.sortie_jour == "2020-01-03"


def test_sortie_sur_signal_nommee():
    o, h, lo, c = _cas()
    (t,) = _run(o, h, lo, c, flat=(4,))["trades"]
    assert (t.sortie_jour, t.motif_sortie) == ("2020-01-06", "signal")


def test_sans_niveaux_le_moteur_est_inchange():
    o, h, lo, c = _cas()
    a = simuler(_jours(), o, c, _sig(1), _sig(5), debut=_jours()[0], cout=0.001)
    b = simuler(_jours(), o, c, _sig(1), _sig(5), debut=_jours()[0], cout=0.001, haut=h, bas=lo,
                stops=np.full(N, np.nan), cibles=np.full(N, np.nan))
    assert a["equity"] == pytest.approx(b["equity"]) and a["trades"] == b["trades"]


def test_duree_fractionnaire_en_intraday():
    j = [f"2024-01-01T{k:02d}:00:00" for k in range(N)]
    o = c = np.full(N, 100.0)
    r = simuler(j, o, c, _sig(1), _sig(7), debut=j[0], cout=0.0)
    assert r["trades"][0].jours == pytest.approx(6 / 24)
