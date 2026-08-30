# Robot price-action causal — périmètre et protocole

## Statut honnête

Ce module est une **hypothèse de recherche UNCALIBRATED**, pas une preuve d'alpha. Des barres OHLCV
ne révèlent ni le carnet d'ordres historique, ni les ordres institutionnels. Les termes BOS, FVG,
order block et SFP sont traduits en règles de prix falsifiables ; ils ne prouvent pas l'intention
d'un intervenant. Le filtre de volume est un proxy volume-prix, jamais un vrai Volume Profile sans
données tick ou L2.

## Logique causale d'un trade

1. Les pivots ne sont confirmés qu'après `pivot_span` barres à droite. Un BOS HTF n'existe que
   lorsque la clôture d'une barre HTF **terminée** dépasse un pivot déjà confirmé.
2. Une zone est soit un gap trois-barres, soit la dernière bougie opposée avant une impulsion dont
   le true range dépasse le multiple explicitement fourni et qui casse un pivot.
3. Le premier retour doit atteindre le midpoint de la zone. Tout contact antérieur consomme le FTB.
4. La barre d'entrée doit balayer le dernier pivot opposé et clôturer de l'autre côté (SFP).
5. Si le filtre volume est activé, le prix doit se trouver dans un bin de faible volume à une
   extrémité du profil. Ses paramètres doivent être calibrés train-only.
6. La prochaine ouverture est le premier prix exécutable. Le stop reste derrière la zone. Le TP1
   est la poche de liquidité opposée la plus proche et le setup est refusé si elle vaut moins de 2R.
   La moitié est réalisée au TP1 ; le solde vise au moins 3R.
7. La quantité inclut distance au stop, slippage et commissions afin que le stop complet coûte au
   maximum `equity × risk_fraction`, avec `risk_fraction ≤ 1 %`.

## Utilisation Python

```python
from packages.backtest.price_action import backtest_price_action
from packages.execution.costs import CostModel
from packages.strategies.institutional_price_action import InstitutionalPriceAction

strategy = InstitutionalPriceAction(
    pivot_span=PIVOT_SPAN_TRAIN_ONLY,
    htf_multiple=HTF_MULTIPLE_TRAIN_ONLY,
    displacement_multiple=DISPLACEMENT_TRAIN_ONLY,
    stop_buffer_bps=STOP_BUFFER_FROM_REAL_SPREADS,
    tp2_rr=3.0,
)
result = backtest_price_action(
    bars=real_point_in_time_bars,
    strategy=strategy,
    initial_equity=capital,
    risk_fraction=0.01,
    costs=CostModel(fee_bps=REAL_FEES, slippage_bps=REAL_SLIPPAGE),
)
print(result.expectancy_r, result.win_rate, result.status)
print(strategy.guard_diagnostics())
```

Les identifiants en majuscules sont volontairement non chiffrés : ils doivent provenir des données
réelles et être réajustés dans chaque fold d'entraînement. Le synthétique est réservé aux tests.

## Formulation

- Risque unitaire net au stop : `L = perte_prix_stop + frais_entrée + frais_sortie`.
- Quantité : `q = equity × risk_fraction / L`.
- Multiple réalisé : `R_i = PnL_net_i / risque_initial_i`.
- Espérance : `E[R] = p_win × moyenne(R_win) − (1 − p_win) × moyenne(|R_loss|)`.

## Validation minimale avant toute promotion paper

- Données point-in-time, univers sans survivorship et séparation stricte train/test.
- Walk-forward ou CPCV purgée avec embargo couvrant l'horizon maximal du trade.
- Paramètres de pivots, déplacement, volume et buffer calibrés **dans chaque train seulement**.
- Spreads, commissions, slippage conditionnel, impact racine carrée et borrow pour les shorts.
- Baseline sans chaque confluence pour mesurer sa contribution marginale et ses compteurs de veto.
- DSR, PBO, White Reality Check, stabilité par régime, turnover, capacité et drawdown.
- Si moins de 30 trades fermés : résultat explicitement `UNCALIBRATED`.

## Red team CRO

- BOS/CHoCH et order blocks n'ont pas de définition universelle : le risque de researcher degrees
  of freedom est élevé.
- Le FTB peut être un artefact de résolution : un contact intrabar est inconnu en OHLCV agrégé.
- Si stop et objectif sont touchés dans la même barre, le backtest choisit le stop en premier.
- Un stop serré augmente mécaniquement slippage, gap risk et probabilité de non-exécution au prix.
- Un objectif 3R ne maximise pas automatiquement l'espérance : le win rate peut s'effondrer.
- Aucune activation dans `scripts/run_live.py` n'est réalisée par ce chantier.
