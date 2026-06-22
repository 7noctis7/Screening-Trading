"""Gate de promotion de modèle (champion/challenger) — defense-in-depth ML.

Un modèle ré-entraîné ne remplace l'incumbent (« champion ») QUE s'il est meilleur **hors
échantillon** ET ne régresse pas en calibration. Sinon on garde l'ancien (anti-régression
silencieuse). Métriques attendues : DSR/PSR (Sharpe déflaté/probabiliste, López de Prado) et
Brier (calibration — plus bas = mieux). 100 % numpy/stdlib, aucune dépendance externe.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelMetrics:
    dsr: float = 0.0      # Deflated Sharpe Ratio (ou PSR) OOS — plus haut = mieux
    brier: float = 1.0    # score de Brier OOS — plus bas = mieux (0 = parfait)
    auc: float = 0.5      # ROC-AUC OOS (info) — plus haut = mieux


def should_promote(
    challenger: ModelMetrics,
    champion: ModelMetrics | None,
    *,
    min_dsr: float = 0.0,            # un challenger doit avoir un edge OOS positif
    max_brier: float = 0.25,         # calibration plancher (0.25 = pile/face)
    brier_tolerance: float = 0.02,   # régression de calibration tolérée vs champion
    min_dsr_uplift: float = 0.0,     # gain minimal de DSR pour détrôner le champion
) -> tuple[bool, str]:
    """Renvoie (promouvoir?, raison). Conservateur par défaut : à égalité, on garde le champion."""
    # Garde-fous absolus (un challenger doit être viable en soi)
    if challenger.dsr <= min_dsr:
        return False, f"DSR challenger {challenger.dsr:.3f} ≤ seuil {min_dsr:.3f} (pas d'edge OOS)"
    if challenger.brier > max_brier:
        return False, f"Brier challenger {challenger.brier:.3f} > {max_brier:.3f} (mal calibré)"

    # Premier modèle : on adopte s'il passe les garde-fous absolus.
    if champion is None:
        return True, f"aucun champion — adoption (DSR {challenger.dsr:.3f}, Brier {challenger.brier:.3f})"

    # Champion/challenger : battre le DSR ET ne pas dégrader la calibration.
    if challenger.dsr < champion.dsr + min_dsr_uplift:
        return False, (f"DSR {challenger.dsr:.3f} < champion {champion.dsr:.3f}"
                       f" (+{min_dsr_uplift:.3f}) — on garde le champion")
    if challenger.brier > champion.brier + brier_tolerance:
        return False, (f"calibration en régression : Brier {challenger.brier:.3f} > "
                       f"champion {champion.brier:.3f} + {brier_tolerance:.3f}")
    return True, (f"promu : DSR {challenger.dsr:.3f} ≥ {champion.dsr:.3f} et "
                  f"Brier {challenger.brier:.3f} ≤ {champion.brier + brier_tolerance:.3f}")
