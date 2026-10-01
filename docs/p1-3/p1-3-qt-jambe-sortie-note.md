# P1.3 QT — Jambe sortie (`fee_comm` à la clôture)

**Date :** 2026-10-01 · **Owner wire :** QT · **Scope :** paper-only · **sleeve OFF** · **0 claim α**  
**Draft only** — pas de push, pas de PR, pas de merge.

## Découpe Arch

Barème unique / `CostModel` / `round_trip_bps` / `cout_execution` / assumptions → **Arch**.  
`packages/execution/costs.py` **non touché** (jamais modifié dans ce worktree ; rien à revert).

## Ce qui change (QT)

| Fichier | Changement |
|---------|------------|
| `packages/execution/live_roundtrip.py` `_close_record` | Après `charge = lot.fees + broker_charge(..., side="SELL")` : **`fee_comm=charge`** (en plus de `fees=charge` déjà en place). Formule PnL **inchangée**. |
| idem `_part` | Proportionne aussi `fee_comm` à la scission (comme `fees` / `slippage`) pour éviter un fee_comm open-only entier sur le reste. |
| `tests/execution/test_live_roundtrip.py` | Smoke `test_close_fee_comm_equals_open_plus_sell_charge` : open BUY + close SELL → `fees == fee_comm == buy_charge + sell_charge`. |
| `tests/execution/test_journal_frais_slippage.py` | Assert `ferme.fee_comm == ferme.fees` sur vente partielle ; `_lot` porte `fee_comm=fees`. |

## Jambe sortie — comportement

- Open (`live_journal.build_open`) : déjà `fee_comm = broker_charge BUY`.
- Close : charge SELL déjà branchée ; **manquait** `fee_comm` (restait open-only / None) → corrigé.
- Equity Alpaca exemple (notionnel 1000 $ BUY / 1100 $ SELL) : BUY charge 0 + SELL reg ≈ 0,308 $ → `fee_comm` clôture = total documenté, **pas** ½ RT inventé.

## Chemins ½ RT inventés (journal paper)

Recherche worktree (`live_roundtrip` / `live_journal` / fermeture paper) : **aucun** close paper qui invente ½ RT. Les closes passent par `broker_charge(..., side="SELL")`. Pas de flag `degraded_bps_model` à poser ici. (Les ½ RT lab/backtest via `CostModel.round_trip_bps/2` restent hors scope QT → Arch.)

## Tests

```
pytest tests/execution/test_live_roundtrip.py \
       tests/execution/test_commission_estimee.py \
       tests/execution/test_journal_frais_slippage.py -q
→ 40 passed
```

## Livrables

- Patch : `/workspace/lab-ab-runs/patch-p1-3-qt-fee-comm-close.patch`
- Branche locale worktree : `funddesk/p1-3-qt-jambe-sortie` (commit local only)
- Worktree : `/workspace/Screening-Trading-p13-costs` (depuis `origin/main`)

## Hors scope / non fait

- Unification barème / equity RT 10 → 10,28 → Arch
- Push / PR / merge / sleeve ON / claim α
