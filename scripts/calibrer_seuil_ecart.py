"""Calibre `SEUIL_ECART` sur le VRAI panneau — au lieu de le poser à vue.

  python scripts/calibrer_seuil_ecart.py            # lecture seule, n'écrit rien

POURQUOI. Le seuil de 8 écarts robustes a été posé sans mesure. Sur le premier passage
réel (08/09), il signalait 430 actifs sur 774 : à ce taux, ce n'est plus un détecteur,
c'est un bruit de fond qu'on apprend à ignorer. La cause a été mesurée sur un panneau
SAIN de 774 séries multi-classes : sans normalisation par actif, 100 % des cryptos sont
signalées et 0 % du forex — la coupe du jour mélangeait des échelles (0,5 % / 1,5 % /
5 % par jour) et reprochait à une crypto d'être une crypto.

CE QUE MESURE CE SCRIPT. Deux choses, séparément :

  1. Le TAUX DE FOND : quelle part de l'univers est signalée, par classe, à chaque
     seuil, dans les deux modes. C'est le coût du détecteur : ce qu'un humain doit lire.

  2. La SENSIBILITÉ : on injecte dans le panneau réel des défauts CONNUS — un split ×4
     non ajusté, un tick erroné — et on compte combien ressortent. C'est le bénéfice.

Sans le second, on choisirait le seuil qui parle le moins : l'infini. Sans le premier,
on choisirait celui qui attrape tout : zéro. Le bon seuil se lit sur les deux courbes.

CE QUE CE SCRIPT NE FAIT PAS. Il n'écrit rien et ne change aucun seuil. Il imprime une
PROPOSITION ; changer `SEUIL_ECART` reste un geste humain, séparé et daté.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from packages.storage.anomalies_panel import ecart_a_la_coupe  # noqa: E402

SEUILS = (4.0, 6.0, 8.0, 10.0, 12.0, 16.0, 24.0)
N_INJECTIONS = 40          # assez pour une sensibilité à ±8 points, assez peu pour
                           # que le script reste lançable en fin de session
GRAINE = 0


def _rendements(prix: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.diff(prix, axis=0) / np.where(prix[:-1] == 0, np.nan, prix[:-1])


def _signales(r: np.ndarray, seuil: float, normaliser: bool) -> set[int]:
    return {s["actif_index"] for s in ecart_a_la_coupe(r, seuil, normaliser)}


def taux_de_fond(prix: np.ndarray, classes: list[str], seuil: float,
                 normaliser: bool) -> tuple[float, dict[str, float]]:
    """Part de l'univers signalée, au total et par classe. Le COÛT du détecteur."""
    touches = _signales(_rendements(prix), seuil, normaliser)
    total = len(touches) / max(1, prix.shape[1])
    par_classe: dict[str, float] = {}
    for c in sorted(set(classes)):
        idx = {j for j, x in enumerate(classes) if x == c}
        par_classe[c] = len(touches & idx) / max(1, len(idx))
    return total, par_classe


def _injecter(prix: np.ndarray, cibles: list[int], dates: list[int],
              genre: str) -> np.ndarray:
    """Copie du panneau avec un défaut CONNU par actif ciblé."""
    p = prix.copy()
    for j, t in zip(cibles, dates, strict=True):
        if genre == "split":
            p[t:, j] /= 4.0                 # division non ajustée : −75 % en une séance
        else:
            p[t, j] *= 3.0                  # tick erroné, corrigé le lendemain
    return p


def sensibilite(prix: np.ndarray, seuil: float, normaliser: bool, genre: str,
                n: int = N_INJECTIONS, graine: int = GRAINE) -> float:
    """Part des défauts injectés qui ressortent. Le BÉNÉFICE du détecteur.

    On ne compte QUE les actifs ciblés, et on retire ceux que le détecteur signalait
    déjà avant injection : sinon on créditerait le détecteur d'une série qu'il avait
    trouvée cassée toute seule, et la sensibilité mesurerait le taux de fond.
    """
    g = np.random.default_rng(graine)
    t_max, n_actifs = prix.shape
    cibles = [int(j) for j in g.choice(n_actifs, size=min(n, n_actifs), replace=False)]
    dates = [int(d) for d in g.integers(t_max // 4, 3 * t_max // 4, size=len(cibles))]

    r = _rendements(prix)
    deja = _signales(r, seuil, normaliser)
    naifs = [j for j in cibles if j not in deja]
    if not naifs:
        return float("nan")
    gardes = [(j, t) for j, t in zip(cibles, dates, strict=True) if j in set(naifs)]
    pollue = _injecter(prix, [j for j, _ in gardes], [t for _, t in gardes], genre)
    trouves = _signales(_rendements(pollue), seuil, normaliser)
    return len({j for j, _ in gardes} & trouves) / len(gardes)


def _ligne(seuil: float, fond: float, par_classe: dict[str, float],
           sens: dict[str, float]) -> str:
    classes = "  ".join(f"{c[:6]} {100 * v:3.0f}%" for c, v in par_classe.items())
    return (f"  {seuil:5.1f} │ fond {100 * fond:5.1f}%  │ "
            f"split {100 * sens['split']:3.0f}%  tick {100 * sens['tick']:3.0f}%  │ "
            f"{classes}")


def rapport(prix: np.ndarray, classes: list[str], normaliser: bool) -> list[dict]:
    mode = ("AVEC normalisation par actif" if normaliser
            else "SANS normalisation (ancien mode)")
    print(f"\n  {mode}")
    print(f"  {'seuil':>5} │ {'coût':^13} │ "
          f"{'sensibilité (défauts injectés)':^28} │ par classe")
    mesures = []
    for s in SEUILS:
        fond, par_classe = taux_de_fond(prix, classes, s, normaliser)
        sens = {g: sensibilite(prix, s, normaliser, g) for g in ("split", "tick")}
        mesures.append({"seuil": s, "fond": fond, "par_classe": par_classe, **sens})
        print(_ligne(s, fond, par_classe, sens))
    return mesures


def proposer(mesures: list[dict]) -> None:
    """Le seuil qui maximise (sensibilité moyenne − taux de fond). Une PROPOSITION."""
    scores = [(np.nanmean([m["split"], m["tick"]]) - m["fond"], m) for m in mesures]
    scores = [(s, m) for s, m in scores if np.isfinite(s)]
    if not scores:
        print("\n  UNCALIBRATED — aucune mesure exploitable.")
        return
    meilleur = max(scores, key=lambda x: x[0])[1]
    print(f"\n  PROPOSITION : SEUIL_ECART = {meilleur['seuil']:.0f}")
    print(f"    · signale {100 * meilleur['fond']:.1f} % de l'univers "
          "(ce qu'un humain doit lire)")
    print(f"    · retrouve {100 * meilleur['split']:.0f} % des splits injectés, "
          f"{100 * meilleur['tick']:.0f} % des ticks erronés")
    print("    Rien n'est écrit : changer le seuil reste un geste humain, daté, dans")
    print("    packages/storage/anomalies_panel.py.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jours", type=int, default=1500)
    ap.add_argument("--comparer-ancien", action="store_true",
                    help="mesure aussi le mode SANS normalisation (2× plus long)")
    a = ap.parse_args()

    from scripts.valider_nouveautes import charger_panel
    champs, symboles, mode, classes = charger_panel(a.jours)
    prix = champs["close"]
    print(f"\nPanneau RÉEL : {prix.shape[0]} dates × {prix.shape[1]} actifs "
          f"(source : {mode})")
    repartition = ", ".join(f"{c}={classes.count(c)}" for c in sorted(set(classes)))
    print(f"Classes : {repartition}")

    if a.comparer_ancien:
        rapport(prix, classes, normaliser=False)
    mesures = rapport(prix, classes, normaliser=True)
    proposer(mesures)


if __name__ == "__main__":
    main()
