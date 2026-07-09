# Étude de cas — Construire un *gate d'honnêteté* anti-fuite pour la recherche quantitative

> Comment j'ai conçu un pipeline qui **rejette** les fausses découvertes de trading avant qu'elles
> ne coûtent de l'argent — et pourquoi il a rejeté 8 de mes propres hypothèses sur 8.
> *Auteur : builder solo · Stack : Python 3.11, NumPy/SciPy, SQLite, FastAPI, Next.js · 825 tests, CI.*

## Le problème (pourquoi 90 % des backtests mentent)
Un backtest qui « marche » ne prouve rien. Trois tueurs silencieux, tous présents chez les
débutants comme chez les pros pressés :

1. **Fuite de données / look-ahead** — utiliser une information non disponible à l'instant *t*
   (fondamentaux révisés, univers filtré avec la qualité d'aujourd'hui, prix non ajustés des splits).
2. **Multiple testing** — essayer 50 stratégies et garder la meilleure : le Sharpe « gagnant » est
   du bruit sélectionné. C'est le péché capital de la recherche quant.
3. **Sur-optimisation** — des paramètres calés sur le passé qui s'effondrent hors échantillon.

La plupart des projets « résolvent » ça en… ne les mesurant pas. Mon choix inverse : **rendre
impossible de se mentir**, et publier chaque verdict, positif ou négatif.

## La solution — un gate à 4 étages (aucun signal en prod sans les 4)
Chaque hypothèse d'alpha traverse, dans l'ordre, quatre filtres orthogonaux
(`packages/research/`). Un seul échec = rejet, consigné au registre.

| Étage | Question | Méthode | Seuil |
|---|---|---|---|
| **1. Placebo** | Le signal bat-il le hasard ? | Permutation : on rejoue le signal sur des étiquettes mélangées, N fois | p < 0,05 |
| **2. Deflated Sharpe (DSR)** | Le Sharpe survit-il au nombre d'essais ? | López de Prado : PSR corrigé de skew/kurtosis **et du nombre de configs testées** | DSR > 0,5 |
| **3. PBO / CSCV** | Le meilleur in-sample reste-t-il bon out-of-sample ? | Combinatorially-Symmetric Cross-Validation → probabilité d'overfit backtest | PBO < 0,5 |
| **4. Sabotage adverse** | L'edge survit-il au réel dégradé ? | Stress : coûts ×3, latence, bruit d'exécution → taux de rétention de l'edge | rétention > 0 |

Le point clé (López de Prado) : l'étage 2 **pénalise explicitement le nombre d'essais**. Tester
20 configurations et garder la meilleure divise le Sharpe requis — le DSR le sait, et il refuse.

## Preuve que le gate a des dents : il m'a rejeté 8 fois sur 8
Ce ne sont pas des exemples théoriques — ce sont mes vraies hypothèses, publiées dans le
[Registre des échecs](https://7noctis7.github.io/Screening-Trading/echecs) :

- **Fear & Greed contrarian sur BTC** → placebo p = 0,905 (bruit pur). Rejeté.
- **Cassure de canal (channel break)** → DSR = 0, PBO = 0,88 sur 20 configs. Rejeté.
- **PEAD cross-sectionnel, TVL/MCap on-chain, momentum overnight…** → tous rejetés au gate.

**Conclusion assumée : DSR≈0. Le système n'a pas d'alpha directionnel prouvé.** Le seul edge qui
survit est la **réduction du drawdown (~2,6× vs équipondéré)** — un edge de *risque*, pas de
direction. Le dire au lieu de le cacher **est** le produit.

## Le piège le plus vicieux que j'ai attrapé (et verrouillé)
En auditant, j'ai trouvé une **fuite d'univers** : trois fonctions du dashboard sélectionnaient
l'univers historique avec le score *qualité d'aujourd'hui* → look-ahead + survivorship. Mesuré :
l'alpha d'attribution tombait de **7,55 % → 4,45 %** une fois corrigé. La fuite gonflait le
résultat de ~3 points.

Le correctif n'est pas seulement le fix — c'est le **verrou de non-régression** :
`tests/backtest/test_dashboard_no_leak.py` passe deux jeux de qualité **opposés** et exige une
sortie **identique** (l'univers ne doit dépendre que du momentum prix-only). Le test vérifie
*aussi* que le mode fuité **diverge** — sinon ce serait un faux positif rassurant. Un test sans
mordant ne prouve rien.

## Rigueur point-in-time (les détails qui séparent l'amateur du pro)
- **Prix ajustés splits/dividendes** + détection de « couture » : si un split est passé depuis la
  dernière ingestion, re-backfill complet du symbole (jamais deux référentiels collés).
- **Vintages macro réels (ALFRED)** : chaque révision est datée de *sa publication*, pas de la
  date d'observation → un backtest d'avril ne voit pas le CPI de mars révisé en juin.
- **Fondamentaux datés au dépôt** (`fillingDate`), pas à la clôture d'exercice.
- **Sentinelle anti-fuite** (`pit_guard.py`) : `assert_no_leak`, `stable_prefix`.

## Architecture (pourquoi ça reste maintenable)
- **Plugins auto-enregistrés** (`packages/core/registry.py`) : ajouter une stratégie / un facteur /
  une source = **1 fichier**, jamais toucher au cœur.
- **Isolation des fautes** (`safe_section`) : une section qui plante ne tue pas le snapshot entier.
- **Séparation stricte des sources** dans le journal : features figées à la *décision*, faits
  d'exécution lus du broker *après* fill — jamais mélangés, jamais inventés.
- **Un seul chemin de production** (`run_live.py`), le reste rétrogradé en simulation (ADR-0031).

## Ce que ça démontre
Capacité à : (1) raisonner statistiquement sur la validité d'une stratégie (López de Prado
appliqué, pas récité) ; (2) traquer le look-ahead jusque dans ses recoins ; (3) construire des
tests qui **prouvent** l'absence de régression ; (4) préférer une vérité inconfortable (DSR≈0) à un
chiffre flatteur. **En quant, cette discipline vaut plus que n'importe quel alpha prétendu.**

---
*Code : [`packages/research/`](../packages/research) (gate) · [`packages/portfolio/psr.py`](../packages/portfolio/psr.py)
(DSR/PBO) · [`packages/common/pit_guard.py`](../packages/common/pit_guard.py) (anti-fuite).
Verdict live : `make rdv-paper` (GO/NO-GO mécanique, RDV paper 2026-08-06).*
