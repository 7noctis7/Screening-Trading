# P1.3 — Coûts unifiés (barèmes + jambe sortie)

**GO DM** 2026-10-01 · paper-only · **sleeve OFF** · queue post QML  
**Owner métriques :** TCA Desk · wire : QT / Arch · consommateurs : Risk / TCA / ML

## Écart actuel

| Source | Où | Contenu | Problème |
|--------|-----|---------|----------|
| `_COST_BY_CLASS` / `CostModel` | backtests, preset_curves, labs levier, Frictions shadow | equity RT = **10 bps** (2×(2+3)) | Barème « classe retail » ≠ courtier réel |
| `BROKER_FEES` / `broker_fee` | `preset_livre`, sizing realist | Alpaca : 0 comm + 5 slip + **reg 0,28 bps SELL** | Vérité courtier, peu lue hors livre |
| `broker_charge` | `live_journal` open, `live_roundtrip` close | comm + reg **sans** slip (slip dans prix) | Correct pour journal ; open = **BUY only** |
| `broker_assumptions().round_trip_bps` | UI / tables | `2×(comm+slip)` | **Oublie reg SELL** → RT equity sous-estimé |
| Frais UI compte | `frais_store` | Cumul Alpaca FEE/CFEE | Tuyau parfois non branché (cf. `quant-trader-costs-report.md`) |

**Jambe sortie :** roundtrip close OK (`broker_charge SELL`) ; beaucoup de chemins lab/backtest taxent **½ RT symétrique** sans SEC/TAF ; opens journal n’accumulent pas la jambe sortie tant que le lot n’est pas clôturé → PnL net entry-only biaisé si on lit `fees` open comme RT.

**Conséquence Risk/TCA/ML :** trois chiffres « 10 bps » / « broker_fee » / « charge sans slip » non interchangeables → ρ_cost, gates, labels ML **incomparables**.

## Plan 3L

1. **Barème unique** — API `cout_execution(ac, notional, side)` = `broker_fee`/`broker_charge` selon usage (prix vs débit) ; `CostModel.for_asset_class` **dérivé** de `BROKER_FEES[broker_for(ac)]` (plus de `_COST_BY_CLASS` divergent) ; RT bps = `2×(comm+slip) + reg_bps`.
2. **Jambe sortie** — tout close paper/backtest appelle charge `SELL` + champ `fee_comm` sortie (nullable) ; smoke : open BUY + close SELL = RT documenté ; pas de ½ RT inventé sans flag `degraded_bps_model`.
3. **Parité Risk/TCA/ML** — un helper partagé `round_trip_bps(ac)` ; tests 3 call-sites (Risk gate, TCA attribution, label coût ML) bit-identiques ; **sleeve OFF** ; pas de PR sans cascade.

## Hors scope
Live enable · sleeve swing ON · merge bande 0.03 · claim α.

## Next
QT/Arch : patch minimal `costs.py` + 1 test parité + wire close SELL manquants. TCA revalide tables assumptions.
