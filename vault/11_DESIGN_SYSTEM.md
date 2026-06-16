# 11 — DESIGN SYSTEM

> Source de vérité des tokens (miroir : `apps/web/lib/tokens.ts` + `tailwind.config.ts`).
> Philosophie Apple : **clarté** (la donnée est la star), **déférence** (l'UI s'efface),
> **profondeur/fluidité**. Couleurs sobres ; **vert/rouge réservés au P&L et au régime**.

## Couleurs (dark natif)
| Token | Hex | Usage |
|---|---|---|
| bg | #0a0b0d | fond global |
| surface | #141619 | cartes |
| surfaceAlt | #1b1e23 | survol/zones |
| border | #262a31 | séparateurs |
| text | #e6e8eb | texte principal |
| textMuted | #9aa1ab | secondaire |
| accent | #3b82f6 | sélection, courbe portefeuille |
| pnlPos / pnlNeg | #22c55e / #ef4444 | P&L uniquement |
| cycle | expansion #22c55e · recovery #3b82f6 · slowdown #f59e0b · recession #ef4444 |

## Typo / espacement / rayons
- Police : SF Pro / -apple-system ; chiffres **tabular-nums** (mono) pour l'alignement.
- Échelle d'espacement : multiples de 4px. Rayons : 8 / 12 / 16px.
- Densité maîtrisée : drill-down progressif, pas d'entassement.

## Composants (shadcn/ui + Radix)
MetricCard · RegimeBanner · table dense (TanStack Table) · EquityChart (Lightweight Charts) ·
heatmap de corrélation (visx/Recharts) · panneau « revue experte ».

## Écrans
Dashboard (✅ scaffold + aperçu) · Screener · Détail actif · Portefeuille/Analyse
(composition, benchmarks rebasés, corrélation, revue experte, risque, historique trades) ·
Trading/positions (kill-switch visible) · Recherche/Backtest (tear sheets).

## Accessibilité & perf
Contraste AA/AAA, navigation clavier, responsive ; skeletons + optimistic UI ; 60 fps.
