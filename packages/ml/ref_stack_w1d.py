"""Alignement REF stack HTF Weekly (ISO) + signal 1d — paper-only, 0 claim, pas DL.

Contexte campagne Levier 4 (panel freeze 725 / n_eff 644 L2 ; L3 ACCEPT_REFERENCE
W LO Sharpe 1.13). Ce module NE pousse rien en prod : helper local pour coller
labels + purged CV + features PIT au contrat W+1d.

Contrats :
  * Labels : horizon calendaire jusqu'à la clôture ISO-week (HTF W), pas un compte
    de barres 1d aveugle.
  * CV : t0/t1 = ``validation_edge.bornes_label`` (ordinaux calendaires) → PurgedKFold.
  * Features : freeze PIT à la barre signal 1d ; HTF W = dernière semaine ISO
    **terminée** (close-only, as-of signal).
  * Claim futur (hors scope) : gate 4 étages placebo≥200 + edge>0 vs B&H 0.871.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Sequence

import numpy as np

# Figé campagne (ne pas recalculer ici — lecture seule pour doc / asserts soft).
PANEL_FREEZE_N = 725
N_EFF_L2 = 644
BH_CONTROL_SHARPE = 0.871
PLACEBO_CLAIM_MIN = 200
REF_HTF = "W"
REF_SIGNAL_TF = "1d"


def iso_week_end(ts: datetime) -> datetime:
    """Dimanche de la semaine ISO contenant ``ts`` (fin de barre W calendaire)."""
    # ISO : lundi=1 … dimanche=7
    wd = ts.isoweekday()
    return (ts + timedelta(days=(7 - wd))).replace(
        hour=0, minute=0, second=0, microsecond=0
    )


def horizon_bars_to_htf_w(bars_1d: Sequence[Any], entry_idx: int) -> int:
    """Nombre de barres 1d jusqu'à (et y compris) la fin de semaine ISO de l'entrée.

    Si l'entrée tombe en fin de semaine déjà close, horizon = 0 barres forward utiles
    pour un label W — l'appelant doit avancer au signal suivant.
    """
    ts = bars_1d[entry_idx].ts
    if hasattr(ts, "to_pydatetime"):
        ts = ts.to_pydatetime()
    end = iso_week_end(ts)
    # Cherche la dernière barre 1d dont ts.date() <= end.date()
    j = entry_idx
    n = len(bars_1d)
    while j + 1 < n:
        t2 = bars_1d[j + 1].ts
        if hasattr(t2, "to_pydatetime"):
            t2 = t2.to_pydatetime()
        if t2.date() > end.date():
            break
        j += 1
    return max(0, j - entry_idx)


@dataclass(slots=True)
class BornesCalendaires:
    entry_idx: int
    exit_idx: int
    t0: int  # ordinal calendaire
    t1: int


def bornes_label_htf_w(bars_1d: Sequence[Any], entry_idx: int) -> BornesCalendaires:
    """Bornes label alignées HTF W : t0/t1 via ordinaux (même contrat que bornes_label).

    Réutilise la sémantique de ``packages.ml.validation_edge.bornes_label`` une fois
    l'horizon ramené à la fin de semaine ISO.
    """
    from packages.ml.validation_edge import bornes_label

    h = horizon_bars_to_htf_w(bars_1d, entry_idx)
    if entry_idx + h >= len(bars_1d):
        h = len(bars_1d) - 1 - entry_idx
    t0, t1 = bornes_label(list(bars_1d), entry_idx, h)
    return BornesCalendaires(entry_idx, entry_idx + h, t0, t1)


def purged_splits_from_bornes(
    bornes: Sequence[BornesCalendaires],
    n_splits: int = 5,
    embargo_pct: float = 0.01,
):
    """PurgedKFold sur t0/t1 calendaires issus de ``bornes_label_htf_w``."""
    from packages.ml.cv import PurgedKFold

    t0 = np.array([b.t0 for b in bornes], dtype=int)
    t1 = np.array([b.t1 for b in bornes], dtype=int)
    # Tri chronologique obligatoire (cpcv lève ; cv ne vérifie pas — on force ici).
    order = np.argsort(t0, kind="mergesort")
    t0, t1 = t0[order], t1[order]
    cv = PurgedKFold(n_splits=n_splits, embargo_pct=embargo_pct, label_horizon=0)
    for train, test in cv.split(t0, t1):
        yield order[train], order[test]


def last_completed_htf_w_idx(bars_1d: Sequence[Any], signal_idx: int) -> int | None:
    """Index 1d de la dernière barre appartenant à une semaine ISO **terminée** avant signal.

    PIT strict : à la barre signal 1d ``i``, on n'utilise que des closes W déjà connues
    (semaine précédente close). Close-only.
    """
    ts = bars_1d[signal_idx].ts
    if hasattr(ts, "to_pydatetime"):
        ts = ts.to_pydatetime()
    # Fin de la semaine précédente (exclut la semaine en cours même si dimanche partiel).
    this_week_end = iso_week_end(ts)
    prev_week_end = this_week_end - timedelta(days=7)
    # Si on est après la clôture de la semaine courante (lundi suivant…), la semaine
    # courante est close — mais en close-only 1d, on n'a la W que le dimanche/dernier
    # jour présent. Pour rester conservateur : n'accepter que prev_week_end sauf si
    # la barre signal est strictement après this_week_end.
    cutoff = prev_week_end
    if ts.date() > this_week_end.date():
        cutoff = this_week_end
    best = None
    for j in range(signal_idx, -1, -1):
        t2 = bars_1d[j].ts
        if hasattr(t2, "to_pydatetime"):
            t2 = t2.to_pydatetime()
        if t2.date() <= cutoff.date():
            best = j
            break
    return best


def pit_feature_row_close_only(
    feats_1d: dict[str, Sequence[float | None]],
    feats_w_on_1d_index: dict[str, Sequence[float | None]],
    signal_idx: int,
    htf_idx: int | None,
) -> dict[str, float | None]:
    """Freeze PIT à la barre signal 1d + features HTF W as-of dernière W close.

    ``feats_w_on_1d_index`` doit déjà être forward-filled **causalement** jusqu'à la
    barre htf (pas au-delà du signal). Ici on ne lit que ``htf_idx`` et ``signal_idx``.
    """
    row: dict[str, float | None] = {}
    for k, series in feats_1d.items():
        v = series[signal_idx]
        row[f"1d.{k}"] = None if v is None else float(v)
    if htf_idx is None:
        for k in feats_w_on_1d_index:
            row[f"W.{k}"] = None
    else:
        for k, series in feats_w_on_1d_index.items():
            v = series[htf_idx]
            row[f"W.{k}"] = None if v is None else float(v)
    return row


def assert_campaign_constants(*, n_eff: int | None = None, claim: bool = False) -> None:
    """Garde-fous soft : 0 claim, paper-only. N'autorise pas claim si placebo non prêt."""
    if claim:
        raise AssertionError(
            "0 claim : gate futur placebo≥200 + edge>0 vs B&H "
            f"{BH_CONTROL_SHARPE} — ne pas activer ici"
        )
    if n_eff is not None and n_eff != N_EFF_L2:
        raise AssertionError(
            f"panel n_eff attendu {N_EFF_L2} (freeze {PANEL_FREEZE_N}), reçu {n_eff}"
        )
