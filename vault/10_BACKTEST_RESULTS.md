# 10 — BACKTEST RESULTS

> Résultats datés + hash de config + version données (DVC à venir).
> **Toujours OOS / walk-forward + deflated Sharpe.** Un Sharpe in-sample ne vaut rien.

## Méthodologie (S5)
- **Walk-forward** : fenêtres roulantes train→test (warm-up pour indicateurs valides),
  sélection params in-sample, évaluation **out-of-sample**, segments OOS concaténés.
- **Deflated Sharpe (DSR)** : corrige le multiple testing (nb total d'essais = grille ×
  fenêtres). Règle : ne passer en prod qu'avec **DSR élevé** (~>0.95). PSR en complément.

## Journal des runs
| Date | Stratégie | Données | Fenêtres | Essais | OOS Sharpe | PSR | DSR | Verdict |
|---|---|---|---|---|---|---|---|---|
| S5 (démo) | ma_crossover | synthétique seed=7 (4 actifs, 7 ans) | 16 | 64 | 0.46 | 0.90 | 0.00 | NON significatif |

> ⚠️ Données SYNTHÉTIQUES : aucune conclusion d'edge. Le DSR=0 confirme juste que le
> pipeline ne fabrique pas d'alpha. Refaire sur données réelles (yfinance/FMP) ensuite.

---

## 2026-09-03 — Cœur multi-actifs (QQQ + obligations longues + or) — **REJETÉ par la règle**

**Protocole.** Part de cœur figée à 50 %, identique à la production : SEULE la composition
change. Règle d'acceptation écrite AVANT le run (ADR-0053). 24 essais comptés dans la
déflation. Fenêtre commune 2016-05-31 → 2026-09-02, 2 580 séances. Rééq. mensuel du cœur à
5 bps ; le cœur QQQ ne paie aucun rééquilibrage → comparaison défavorable au nouveau venu.

**La prémisse de la construction TIENT.** Corrélations quotidiennes : GLD/QQQ **+0,11**,
QQQ/TLT **−0,09**, GLD/TLT +0,25. Les diversifiants sont réellement décorrélés du Nasdaq —
ce n'est pas là que ça échoue.

| variante | CAGR | Sharpe | Sortino | maxDD | PSR | DSR | ΔSharpe | p |
|---|---|---|---|---|---|---|---|---|
| **PRODUCTION 50 % QQQ** | **15,3 %** | **0,96** | 0,90 | −25,3 % | 100 % | 86 % | — | — |
| contrôle QQQ ETF | 14,9 % | 0,94 | 0,88 | −25,3 % | 100 % | 84 % | −0,02 | **0,000** |
| multi 60/25/15 | 11,4 % | 0,92 | 0,87 | −20,9 % | 100 % | 83 % | −0,03 | 0,674 |
| multi 50/30/20 | 10,6 % | 0,92 | 0,87 | −20,2 % | 100 % | 83 % | −0,04 | 0,684 |
| multi 40/35/25 | 9,8 % | 0,90 | 0,86 | −19,5 % | 100 % | 81 % | −0,06 | 0,650 |
| multi inverse-vol | 9,1 % | 0,90 | 0,87 | **−17,1 %** | 100 % | 81 % | −0,06 | 0,750 |

**Verdict : aucune variante ne passe.** Le critère (a) échoue partout — tous les ΔSharpe
sont NÉGATIFS, avec p entre 0,65 et 0,75 (indiscernables de zéro). Le cœur QQQ reste.

**L'issue secondaire déclarée d'avance s'est produite** : trois variantes améliorent le
maxDD de plus de 5 points (jusqu'à **−8,2 pts** pour l'inverse-vol, soit un tiers du
drawdown en moins). Ce n'était PAS un feu vert automatique, et l'analyse qui suit explique
pourquoi ça n'en devient pas un.

**LA RÉDUCTION DE RISQUE COÛTE PLUS QU'ELLE NE RAPPORTE.** Sur le rendement par unité de
drawdown (Calmar), la production reste devant PARTOUT :

| | CAGR / |maxDD| |
|---|---|
| PRODUCTION | **0,605** |
| contrôle ETF | 0,589 |
| inverse-vol | 0,532 |
| 60/25/15 | 0,545 |
| 50/30/20 | 0,525 |
| 40/35/25 | 0,503 |

Le maxDD baisse de 8,2 points, mais le CAGR baisse de 6,2 points — proportionnellement
plus. Et le levier ne rattrape rien : **le Sharpe est la mesure invariante au levier**, et
c'est précisément lui qui ne s'améliore pas. Lever le cœur diversifié jusqu'au drawdown de
production redonnerait ~13,5 % de CAGR avant coût de financement, contre 15,3 %.

**LIMITE DE L'ÉCHANTILLON, DITE SANS EN FAIRE UN PRÉTEXTE.** La fenêtre contient 2022, pire
année obligataire depuis un siècle (TLT ≈ −31 %). Le test est donc défavorable aux
obligations. Ce n'est PAS une raison de rejouer sur une autre fenêtre : choisir la période
après avoir vu le résultat est exactement ce que la déflation du DSR punit. Le chiffre reste
tel quel.

**FINDING SECONDAIRE, PLUS IMPORTANT QUE LE VERDICT (P1).** La ligne de contrôle — le QQQ
ETF replacé sur l'axe du preset — rend **−0,4 %/an** de moins que le cœur de production,
avec **t(α) = −6,15** et p = 0,000. Écart minuscule, mais massivement significatif, sur une
ligne censée mesurer le MÊME actif. Deux causes possibles, aux conséquences très
différentes : soit `choose_history` retient **^NDX**, un indice non achetable (le tableau de
bord surestimerait alors la moitié « cœur » de ~0,4 %/an, en permanence), soit
`blend_equity` désaligne positionnellement (`core_ret[-k:] = xr[-k:]`) le cœur et l'axe du
preset — quatrième occurrence du même défaut. `make diag-coeur-qqq` tranche entre les deux.

**Ce que le verdict ne doit PAS à cette anomalie** : les variantes multi-actifs perdent
aussi contre la ligne de CONTRÔLE (0,90-0,92 contre 0,94), qui est, elle, correctement
alignée par date. Le rejet tient quelle que soit l'issue du diagnostic.

---

## 2026-09-03 — Fenêtre vs code : le Sharpe 1,33 est reproduit à l'identique

`QUANT_HISTORY_DAYS=3600 make index-core`. Objectif : savoir si la baisse observée
(Sharpe 1,34 → 0,95) venait de la fenêtre de mesure ou d'une régression du code.

**Réponse : la fenêtre.** Blend 50 % QQQ + 50 % preset → Sharpe **1,33**, contre 1,33 dans
l'ancien tableau et 0,96 sur le plein historique. Le backtest actuel démarre treize mois
plus tôt et inclut une période plus difficile.

**À fenêtre égale, le code a amélioré le portefeuille** (preset pur) : Sharpe 0,99 → 1,12,
maxDD −31,7 % → −25,4 %, pour 3 points de CAGR en moins. Les correctifs d'alignement ont
retiré du rendement qui venait avec un risque disproportionné.

| Cœur QQQ | CAGR | Sharpe | Sortino | maxDD | DSR | ΔSharpe vs 50 % | p |
|---|---|---|---|---|---|---|---|
| 0 % | 14,7 % | 1,12 | 1,58 | −25,4 % | 91 % | −0,21 | 0,522 |
| 25 % | 16,9 % | **1,42** | 2,09 | **−18,2 %** | 99 % | +0,09 | 0,612 |
| **50 % (prod)** | 18,5 % | 1,33 | 1,96 | −22,4 % | 98 % | — | — |
| 75 % | 19,6 % | 1,09 | 1,57 | −28,7 % | 90 % | −0,24 | **0,027** |
| 100 % | 20,2 % | 0,91 | 1,29 | −35,1 % | 77 % | −0,42 | **0,011** |

**La ligne 25 % ne déclenche aucun changement.** Elle bat la production sur le Sharpe ET le
drawdown, mais p = 0,612 pour un seuil détectable de ±0,29 : c'est du bruit de sélection sur
cinq ratios. Seuls 75 % et 100 % sont discernables — et dans le sens PIRE.

**Alerte non résolue** : le cœur « momentum sectoriel » affiche CAGR 55,5 % à 100 % et
26,8 % à 25 %, DSR 100 %. Un tel chiffre sur 9,4 ans appelle un audit de fuite et de biais du
survivant avant toute lecture. Aucune conclusion n'en est tirée ici.

