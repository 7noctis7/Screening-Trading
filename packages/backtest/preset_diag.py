"""Pourquoi le preset ne demande-t-il RIEN ? — la question sans réponse.

`preset_latest_weights` peut renvoyer un dictionnaire VIDE pour au moins six
raisons, et n'en distingue aucune : trop peu de titres éligibles, aucun score
qualité (repli silencieux sur un univers arbitraire), panel trop court après
intersection des dates, fenêtre de covariance insuffisante, exposition brute
annulée par une porte, ou concentration qui balaie la poussière.

Constat du 26/08 : le compte paper ne contenait AUCUNE action du satellite.
Trois hypothèses successives — plancher de ligne, horaires de marché, mode
léger — se sont toutes révélées fausses, précisément parce qu'aucune trace ne
disait où la chaîne s'arrêtait. Le coût du silence a dépassé celui du défaut.

Ce module ne change AUCUN chiffre. Il enregistre, à chaque étage, ce qui entre,
ce qui sort, et pourquoi — puis le rend lisible.
"""

from __future__ import annotations


class Diag:
    """Journal des étages de `preset_latest_weights`. Observationnel."""

    def __init__(self) -> None:
        self.etapes: list[tuple[str, str]] = []
        self.arret: str = ""
        self.gross: dict[str, float] = {}

    def note(self, etape: str, detail: str) -> None:
        self.etapes.append((etape, detail))

    def stop(self, motif: str) -> Diag:
        """Étage où la chaîne s'arrête. Le PREMIER gagne : c'est la cause."""
        if not self.arret:
            self.arret = motif
        return self

    def porte(self, nom: str, mult: float) -> None:
        """Effet multiplicatif d'une porte (1,0 = sans effet)."""
        self.gross[nom] = round(float(mult), 4)

    @property
    def bloque(self) -> bool:
        return bool(self.arret)

    def resume(self) -> str:
        """Une ligne par étage, puis la cause d'arrêt éventuelle."""
        lignes = [f"  {e:<22} {d}" for e, d in self.etapes]
        if self.gross:
            detail = " × ".join(f"{k} {v:.3f}" for k, v in self.gross.items())
            total = 1.0
            for v in self.gross.values():
                total *= v
            lignes.append(f"  {'exposition brute':<22} {detail}  =  {total:.4f}")
        if self.arret:
            lignes.append(f"  ⛔ ARRÊT : {self.arret}")
        return "\n".join(lignes)

    def as_dict(self) -> dict:
        return {"etapes": [{"etape": e, "detail": d} for e, d in self.etapes],
                "portes": dict(self.gross), "arret": self.arret,
                "bloque": self.bloque}
