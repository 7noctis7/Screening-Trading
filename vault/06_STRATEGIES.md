# 06 — STRATEGIES

> 1 section/stratégie : hypothèse, régime favorable, signaux, gestion de position.

## ma_crossover (trend-following) — `packages/strategies/ma_crossover.py`
- **Hypothèse** : les tendances persistent. **Régime favorable** : trending.
- **Entrée** long au croisement haussier SMA(fast) > SMA(slow). **Sortie** : croisement baissier OU stop/target.
- **Gestion** : stop = entrée − `atr_stop`×ATR ; target = entrée + `rr`×`atr_stop`×ATR (R:R par défaut 2.5).

## rsi_reversion (mean-reversion) — `packages/strategies/rsi_reversion.py`
- **Hypothèse** : retour à la moyenne en range. **Régime favorable** : range/calme.
- **Entrée** long si RSI franchit `low` à la baisse. **Sortie** : RSI franchit `exit_level` à la hausse OU stop/target.

## À venir (P1)
breakout/volatility-expansion, pairs/market-neutral (cointégration), short, trailing stop/TP, break-even, scaling in/out, sélection de stratégie selon le régime (Module 2 étape 0).
