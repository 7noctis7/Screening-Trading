# Rapport d'espérance nette — une page

> État au **2026-10-06**. Ce dépôt ne contient aucune donnée de marché ; les quatre
> réponses se calculent sur le VPS par `make rapport-esperance` (une page écrite dans
> `out/rapport_esperance.md`). Tant que ce calcul n'a pas tourné, la réponse est
> **non mesuré** — même là où une mesure voisine existe (dernière colonne).

| # | Question | Valeur | Intervalle 95 % | Ce qui existe, et pourquoi ça ne répond pas |
|---|---|---|---|---|
| 1 | Espérance nette d'un aller-retour, frais et impact compris | **non mesuré** | — | `make turnover-audit` (24/09) : +0,08 % pondéré par position close, mais sur des **lots** (pas des allers-retours au sens défini ci-dessous), frais estimés pour 64 fermetures sur 597, sans impact. |
| 2 | Livre contre QQQ + cash au même drawdown | **non mesuré** | — | Rejeu du 25/09 : à **même volatilité**, ex post, satellite 15,1 % / an contre 13,3 % pour QQQ dilué, **sans intervalle**. Le test ΔSharpe (p = 0,17 le 30/09) compare à QQQ **nu**. |
| 3a | Paris indépendants | **non mesuré** | — | Aucun calcul de N effectif avant ce rapport ; 12 lignes ≠ 12 paris. |
| 3b | IC hors échantillon du classement tradé | **non mesuré** | — | L'IC publié (−0,068, t = −1,98) est celui du score de **screening**, que la production n'utilise pas. |
| 4 | Encours où l'espérance devient nulle | **non mesuré** | — | Aucun calcul de capacité ; le coût du rejeu est un pourcentage fixe. |

**Verdict à ce jour : signal NON établi** (aucune des deux conditions n'est mesurée
positive). Conformément à la règle : pas de pull request de modèle. La pull request
légitime est celle qui retire ce qui coûte.

## Définitions (dans le code, testées)

- **Aller-retour** (`packages/research/aller_retour.py`) : quantité achetée par un ordre
  EXÉCUTÉ (écart qui a franchi la bande et le plancher de `rebalance_plan.decider`),
  revendue par un ordre exécuté, appariée FIFO en quantité ; du prix d'exécution d'achat
  au prix d'exécution de vente. Une détention n'en est pas un.
- **Prix d'exécution** : close de la séance qui SUIT la décision (rejeu, `lag = 1`).
  Les labels de l'IC (`ic_classement`) et du ML (`edge_transversal`) partent de ce prix,
  jamais du close qui a servi au signal.
- **Net** : brut − coût par côté (barème `CostModel`) − impact racine carrée par côté
  (`packages/execution/impact.py`, Y = 0,5 et 1,0 : non calibré, publié en plage).
- **Même risque** : α·QQQ + (1−α)·cash rebalancé chaque jour, α calé sur le drawdown
  maximal (ou la volatilité) du livre, α ≤ 1 ; cash à 0 % (avantage le livre) ; écart
  avec bootstrap en blocs de 20 séances et DSR par le nombre d'essais du registre.
- **Paris indépendants** : N_eff = (Σλ)² / Σλ² des valeurs propres de la corrélation
  des noms détenus (120 séances avant chaque décision), × 252 / détention médiane.
- **Capacité** : encours k × capital où l'espérance nette, impact recalculé à la taille
  k, s'annule ; ADV et σ des 20 séances précédant chaque exécution.

## Retiré, parce que ça coûte sans rien prouver (PR « retirer ce qui coûte »)

- **Rotation de poussière** : la production rebalançait chaque jour alors que la seule
  règle mesurée décide tous les 5 jours. Cadence partagée rejeu / `run_live`
  (`packages/execution/cadence.py`) ; une réduction de risque passe toujours.
- **Multiples inventés** : SEC et yfinance remplaçaient une donnée absente par un multiple
  (marge brute = 40 % du CA, EBIT = 85 % de l'EBITDA…) sous l'étiquette « réel ». Absent
  = NaN, sans note. Le repli synthétique implicite des onglets fondamentaux est retiré.
- **Deux compteurs d'essais** : la porte de déploiement déflatait avec 41 essais, le reste
  avec 5 738. Un seul compteur (5 744 au 06/10).
- **« Promu » à DSR nul** : momentum, trend, low_vol (juin, DSR 0,0 à 0,01) requalifiés
  « rejeté » ; `/api/failures` lit l'état courant.

**Pas retiré, faute de mesure** : l'hystérésis des portes (régime, plafond, blackout)
exige des seuils d'entrée et de sortie qui ne sont pas calibrés. `make rotation-causes`
mesure d'abord la part de la rotation qu'elles causent.

## À lancer sur le VPS

```bash
make rapport-esperance                  # décision tous les 5 j (cadence de production)
make rapport-esperance ARGS="--pas 1"   # ancien rythme quotidien, pour comparer (lent)
```
