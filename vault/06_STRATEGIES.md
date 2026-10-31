# 06 — STRATEGIES

> Une section par stratégie : hypothèse, statut, où elle vit, **verdict mesuré avec sa source**.
> Réécrit le 31/10 : la version précédente ne décrivait que 2 des 13 modules de
> `packages/strategies/`. Aucun chiffre ici n'est neuf : chacun renvoie à sa mesure datée.

## En production (paper) — preset : cœur QQQ 50 % + satellite à risque maîtrisé (ADR-0023)
- **Hypothèse** : le rendement absolu vient de la **bêta honnête** du cœur indiciel
  (`QUANT_CORE_SPEC="qqq:0.5"`) ; le satellite apporte la **gestion du risque**, pas du
  stock-picking. Depuis ADR-0212, la crypto concourt avec les actions sur le momentum.
- **Verdict** : alpha directionnel **non démontré** (DSR ≈ 0, `12_MANIFESTE_HONNETETE`).
  Rapport d'espérance du 07/10 : Q2 +2,95 %/an [−1,40 ; +7,60], DSR 0,01 → NON établi. Le
  seul effet qui tient : IC du momentum 12-1 à 1 jour +0,0190, t = 4,09 (`04_JOURNAL`, 07/10).

## Plugins (`packages/strategies/`, registre `@strategies.register`)

| Module | Hypothèse | Statut | Verdict mesuré (source) |
|---|---|---|---|
| `ma_crossover` | les tendances persistent (régime « trending ») | plugin | 12 actions tirées, 2015+ : aucune règle de timing ne bat l'achat-conservation (Sharpe 0,31–0,49 contre 0,52 ; DSR ≤ 0,45) — `10_BACKTEST_RESULTS`, 30/09 |
| `rsi_reversion` | retour à la moyenne en range | plugin | grille de 480 essais, 4 actifs depuis 2020 : Sharpe médian 0,04, CAGR 0 % — `10_BACKTEST_RESULTS`, 30/09 |
| `swing` | les replis se rachètent en tendance haussière | plugin | même grille : Sharpe 0,17, +1,1 %/an |
| `earnings_pead`, `pead_portfolio` | dérive après résultats (Bernard & Thomas 1989) | recherche | large-cap : p = 0,209 ; small/mid : Sharpe 0,20, DSR 0, PBO 0,76 — rejeté (`12_MANIFESTE_HONNETETE`) |
| `institutional_price_action` | motifs de structure (zones FTB, SFP, profil de volume proxy) | plugin, à calibrer en walk-forward | aucun verdict consigné |
| `moteur_swing` | structure de marché + gestionnaire de risque (spec du 02/09) | `CANDIDATE_UNCALIBRATED` | aucun verdict consigné |
| `moteur_sortie` | sorties par le temps, la liquidité opposée, la divergence de flux | `SHADOW_UNCALIBRATED` | aucun verdict consigné |
| `sorties_suiveuses` | stops suiveurs et prise de gains partielle | `SHADOW_UNCALIBRATED` | grille du 30/09 : suiveur 3 ATR Sharpe 0,44 contre 0,70 pour la sortie sur signal — il coupe la queue droite |
| `conviction` | fusion multi-signaux, z-scores à poids égaux | brique | — |
| `ensemble` | moyenne pondérée de signaux normalisés | brique | — |
| `earnings_blackout` | ne pas porter une position nue à travers une annonce | filtre | — |

## Jamais mesurées (hypothèses ouvertes)
- **Retournement court terme transversal** : acheter les perdants, vendre les gagnants du
  dernier mois, chaque semaine. Aucun passage réel dans `10_BACKTEST_RESULTS`.
- **Momentum en série temporelle** (Moskowitz 2012) : `08_Alphas/ts_momentum.md`, statut
  « hypothèse », DSR et Sharpe vides.

## Règle
Ajouter une stratégie = **un fichier** + `@strategies.register`, jamais le cœur. Aucun verdict
sans le gate à 4 étages (placebo → DSR → PBO → sabotage par les coûts), consigné daté dans
`10_BACKTEST_RESULTS` avec l'empreinte de sa grille, déposée AVANT le calcul.
