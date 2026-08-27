"""Contrôle du taux de FAUSSES DÉCOUVERTES sur un criblage multiple.

La brique manquante, et seulement elle. Le dépôt possède déjà :
  * `portfolio/psr.py`      — PSR et DSR (Bailey & López de Prado), avec la gestion
                              du piège de périodicité (audit du 20/08)
  * `research/ledger.py`    — le registre JSONL des essais, `trial_count`,
                              `deflation_params`
  * `research/gate.py`      — le verdict de promotion (placebo → DSR → PBO → coûts)

Le DSR déflate UN candidat du nombre d'essais. Il ne répond pas à l'autre question :
« parmi N verdicts positifs simultanés, combien sont du bruit ? » Cribler N paires à
p < 0,05 produit 5 % de faux positifs PAR CONSTRUCTION — sur 100 paires, environ cinq
verdicts « tradable » qui ne sont rien. C'est le P0 ouvert de `vault/03_TODO.md` sur
`DualMarketScreening`.

Benjamini-Hochberg (1995) plutôt que Bonferroni : sur des candidats CORRÉLÉS — et des
paires ou des mandats voisins le sont massivement — Bonferroni ne laisse rien passer.
BH accepte une proportion `alpha` de faux positifs parmi les découvertes, ce qui est
la bonne question en criblage.

Zéro dépendance, comme `psr.py` et `ledger.py`.
"""

from __future__ import annotations


def benjamini_hochberg(pvaleurs: list[float], alpha: float = 0.05) -> list[bool]:
    """Rejet de H0 par p-valeur, dans l'ORDRE D'ENTRÉE.

    L'ordre de sortie n'est pas un détail : renvoyer les rejets triés attribuerait
    le verdict au mauvais candidat, en silence.
    """
    m = len(pvaleurs)
    if m == 0:
        return []
    ordre = sorted(range(m), key=lambda i: pvaleurs[i])
    seuil_k = 0
    for rang, i in enumerate(ordre, start=1):
        if pvaleurs[i] <= rang / m * alpha:
            seuil_k = rang
    rejets = [False] * m
    for rang, i in enumerate(ordre, start=1):
        if rang <= seuil_k:
            rejets[i] = True
    return rejets


def resume(pvaleurs: list[float], alpha: float = 0.05) -> dict:
    """Verdict lisible. `n_testees` doit VOYAGER avec le résultat.

    Un « tradable » issu d'un criblage de 500 ne vaut pas celui issu de 5. Publier le
    nombre de candidats testés avec le verdict est la moitié de la correction ; sans
    lui, le lecteur ne peut pas refaire le calcul.
    """
    rejets = benjamini_hochberg(pvaleurs, alpha)
    n_rejets = sum(rejets)
    naifs = sum(1 for p in pvaleurs if p <= alpha)
    return {
        "n_testees": len(pvaleurs),
        "alpha": alpha,
        "n_decouvertes": n_rejets,
        "n_decouvertes_naives": naifs,
        "faux_positifs_attendus_sans_correction": round(len(pvaleurs) * alpha, 2),
        "lecture": (f"{n_rejets} découverte(s) sur {len(pvaleurs)} testée(s) après "
                    f"correction BH ; {naifs} au seuil naïf p<{alpha}, dont "
                    f"~{len(pvaleurs) * alpha:.1f} attendues par pur hasard"),
    }
