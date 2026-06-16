"""Gouvernance des modèles — champion/challenger + registre.

Un nouveau modèle (challenger) ne remplace le champion QUE s'il bat son score OOS d'une
marge minimale ET passe la barrière de risque (pas de dégradation du drawdown). Évite de
déployer un modèle "meilleur par hasard". Registre in-memory (testable) + adaptateur MLflow.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Decision:
    promote: bool
    reason: str


def champion_challenger(challenger_score: float, champion_score: float | None,
                        min_improvement: float = 0.02, risk_ok: bool = True) -> Decision:
    if not risk_ok:
        return Decision(False, "barrière de risque non franchie")
    if champion_score is None:
        return Decision(True, "pas de champion → promotion initiale")
    if challenger_score >= champion_score + min_improvement:
        return Decision(True, f"+{challenger_score - champion_score:.3f} OOS > seuil")
    return Decision(False, f"amélioration insuffisante ({challenger_score - champion_score:+.3f})")


@dataclass
class ModelRegistry:
    """Registre in-memory. En prod : adaptateur MLflow (log params/metrics/artefacts)."""

    _models: dict = field(default_factory=dict)
    champion: str | None = None
    _scores: dict = field(default_factory=dict)

    def register(self, name: str, model, score: float) -> None:
        self._models[name] = model
        self._scores[name] = score

    def champion_score(self) -> float | None:
        return self._scores.get(self.champion) if self.champion else None

    def consider(self, name: str, model, score: float,
                 min_improvement: float = 0.02, risk_ok: bool = True) -> Decision:
        self.register(name, model, score)
        d = champion_challenger(score, self.champion_score(), min_improvement, risk_ok)
        if d.promote:
            self.champion = name
        return d
