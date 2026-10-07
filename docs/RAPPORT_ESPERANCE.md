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
  (`packages/research/capacite.impact` = Y·σ·√(q/ADV), non borné, volumes finis
  seulement ; Y = 0,5 et 1,0 : non calibré, publié en plage, ADR-0217).
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

## Instrumenté depuis (ADR-0216)

- **Coût réel par ordre live** : bid / ask lus avant l'envoi et après les fills
  (Alpaca) ; table `tca_executions` = spread, dérive avant envoi, shortfall d'exécution.
  `make tca` reste UNCALIBRATED sous 20 ordres cotés. C'est l'entrée « frais et impact »
  de la question 1 ; elle n'est recalibrée qu'une fois mesurée.

## Premier passage réel (VPS, 06/10) — ce qui tient et ce qui est à relancer

| Mesure | Résultat | Statut |
|---|---|---|
| 2 · livre − QQQ+cash, même drawdown | +4,24 %/an, IC [−0,10 ; +8,77], DSR 0,06 (5 744 essais) | valable |
| 3 · paris indépendants | 5,3 effectifs pour 12 lignes, 71 / an | valable |
| 3 · IC 2ᵉ moitié | h = 1 j : +0,020 [+0,008 ; +0,032] ; h ≥ 5 j : intervalles contenant 0 | valable (ponctuel et t) |
| 3 · p de permutation | 0,005 partout | **faux** — nulle trop étroite (ADR-0217) |
| 1 · espérance avec impact (Y = 0,5 / 1,0) | +3,77 % / +0,78 % | **faux** — impact saturé (ADR-0217) |
| 4 · capacité | > 10⁶ × / 341 k$ | **faux** — même cause |

Verdict inchangé : **NON établi**.

## Deuxième passage réel (VPS, 07/10) — volumes réparés (#450, #451)

Le premier passage corrigé donnait une participation q/ADV médiane de 42 % : la colonne
`volume` de `market.db` contenait le close (INSERT positionnel sur une table dont
`adj_close` avait été ajouté au bout). Après réparation (48 662 barres échangées par
#451, aucune irrécupérable), même rejeu, 625 séries, 2016-10-12 → 2026-10-07 :

| Mesure | Résultat | Statut |
|---|---|---|
| 4 · participation q / ADV | médiane 0,000 %, p90 0,004 %, max 25 % ; > 1 % : 0,1 % des côtés | **saine** — c'était la condition pour lire 1 et 4 |
| 1 · espérance / aller-retour, frais seuls | +5,84 % [+4,68 ; +7,10], n = 2 215, 57 % gagnants | valable — rendement ABSOLU (bêta compris), pas un alpha |
| 1 · avec impact Y = 0,5 / 1,0 | +5,82 % / +5,80 % | valable — l'impact est négligeable à cette taille |
| 4 · encours d'espérance nulle | 8,3 G$ (Y = 0,5) / 2,1 G$ (Y = 1,0) | extrapolation de la loi racine très loin de toute calibration : lire « la taille n'est pas la contrainte », pas un chiffre |
| 2 · livre − QQQ+cash, même drawdown | +2,95 %/an [−1,42 ; +7,52], DSR 0,01 (5 749 essais) | valable |
| 3 · paris indépendants | 5,2 effectifs pour 12 lignes, 86 / an | valable |
| 3 · IC 2ᵉ moitié, h = 1 j | +0,020 [+0,008 ; +0,032], t 3,71 ; 12-1 : t 4,09 | valable ; h ≥ 5 j non significatif |

Lecture : les coûts ne sont pas ce qui manque. Un aller-retour gagne en moyenne, mais le
livre ne bat pas QQQ + cash au même risque de façon établie (Q2). Verdict **NON établi**.

## À lancer sur le VPS

```bash
make rapport-esperance                  # décision tous les 5 j (cadence de production)
make rapport-esperance ARGS="--pas 1"   # ancien rythme quotidien, pour comparer (lent)
```
