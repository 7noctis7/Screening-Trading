# P1.3 Arch — coûts unifiés (barème unique)

**Date :** 2026-10-01 · **Owner :** Arch Builder · **Scope :** paper-only · **sleeve OFF**
**Pas de commit / push / PR.** Patch local uniquement.

## Ce qui a changé

| Fichier | Changement |
|---------|------------|
| `packages/execution/costs.py` | API `cout_execution(ac, notional, side, *, mode="fee"\|"charge")` ; helper `round_trip_bps(ac)` ; `CostModel.reg_bps` + RT = `2×(fee+slip)+reg` ; `for_asset_class` dérive de `BROKER_FEES[broker_for(ac)]` ; `broker_assumptions` / `cost_assumptions` bit-identiques au helper ; `_COST_BY_CLASS` = shim déprécié (dérivé broker, plus source de vérité) |
| `packages/execution/__init__.py` | Export `round_trip_bps`, `cout_execution` |
| `tests/execution/test_costs.py` | Assertions assumptions incluent `reg_bps` |
| `tests/execution/test_couts_unifies_p13.py` | **nouveau** — RT equity/crypto, parité helper/CostModel/assumptions, cout_execution, smoke 3 call-sites Risk/TCA/ML |

## Formule RT

```
round_trip_bps(ac) = 2 × (commission_bps + slippage_bps) + reg_bps
```

dérivé de `BROKER_FEES[broker_for(ac)]`.

| Classe (défaut) | Courtier | commission | slip | reg | **RT** |
|-----------------|----------|------------|------|-----|--------|
| equity / etf / index | alpaca | 0 | 5 | 0,28 | **10,28** |
| crypto | bitmart | 25 | 12 | 0 | **74** |
| forex / commodity | ibkr | 0,5 | 5 | 0,28 | 11,28 |

## Sleeve / live

- **QUANT_SWING_PAPER** : non touché, reste OFF (défaut).
- Aucun flag sleeve / live enable dans ce patch.

## Tests

```
pytest tests/execution/test_costs.py \
       tests/execution/test_couts_unifies_p13.py \
       tests/backtest/test_couts_derive.py \
       tests/execution/test_commission_estimee.py -q
→ 38 passed
```

(+ `test_frictions` / `test_tca` / `test_impact` / `test_couts_pnl_net` : 33 passed, smoke hors suite formelle.)

## QT — items restants (non Arch)

`live_roundtrip._close_record` charge déjà SELL via `broker_charge` dans `fees` agrégé (entry + exit). **Laisser tel quel.**

Gaps notés pour QT (ne pas inventer ici) :

1. **`fee_comm` sortie** — sur close, `dataclasses.replace` ne met pas à jour `fee_comm` : le champ reste la charge BUY d'entrée. Spec demande un `fee_comm` sortie (nullable) distinct ou mis à jour à la fermeture.
2. **`live_journal.build_open`** — BUY only (correct pour open) ; pas de chemin close dans ce module.
3. Chemins lab/backtest qui taxent ½ RT symétrique sans flag `degraded_bps_model` — hors scope Arch ; désormais le ½ RT vient du barème courtier (10,28/2 au lieu de 10/2 pour equity), ce qui aligne le niveau sans câbler la jambe SELL explicite.

## Patch

`/workspace/p1-3-couts-unifies-arch.patch` (costs.py + __init__.py + test_costs.py + test_couts_unifies_p13.py uniquement — ignore le dirty tree parallèle sleeve/risk/etc.).

## Blockers union QT

Aucun blocker Arch → QT pour le barème. QT peut brancher `fee_comm` exit sur close en important `broker_charge` / `cout_execution(..., mode="charge")` déjà stables. Consommateurs Risk/TCA/ML : one-line swap vers `round_trip_bps(ac)` quand safe (non fait largement ici — smoke parité via 3 wrappers dans le test).
