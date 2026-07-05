# 11 — DESIGN SYSTEM

> **Source de vérité UNIQUE des tokens : `apps/web/app/globals.css`** (variables CSS thème-aware).
> `apps/web/lib/tokens.ts` ne fait que **re-exporter** ces vars (aucune couleur en dur) ; `tailwind.config.ts`
> les mappe en classes. Toute couleur nouvelle se déclare d'abord dans `globals.css`.
> Philosophie : **clarté** (la donnée est la star), **déférence** (l'UI s'efface), **sobriété**.

## Thème
- **Clair par défaut** (`:root`), **sombre** via classe `.dark` sur `<html>` (`ThemeToggle`, persisté localStorage,
  script anti-flash dans `app/layout.tsx`). `darkMode:"class"` côté Tailwind.
- Accents en **OKLCH** en progressive-enhancement (déclarés APRÈS les hex → fallback sûr sans support oklch).

## Couleurs (tokens réels — cyan/teal « bull & bear »)
| Token CSS | Clair | Sombre | Usage |
|---|---|---|---|
| `--bg` / `--surface` | #f4f7f8 / #ffffff | #0a1118 / #121c26 | fond / cartes |
| `--border` / `--border2` | #dde6e8 / #cbd8db | #22303c / #2e3f4d | séparateurs |
| `--fg` / `--muted` / `--muted2` | #0a0f12 / #3f4c55 / #5b6a73 | #eaf2f4 / #93a7b1 / #637580 | textes |
| `--accent` / `--accent2` | cyan #0891b2 / #06b6d4 | #22d3ee / #5eead4 | sélection, courbe portefeuille |
| `--pos` / `--neg` | #16a34a / #dc2626 | #22c55e / #f43f5e | **P&L UNIQUEMENT** (fill plein, vif) |
| `--regime-on` / `--regime-off` | #3f8f6b / #b85c5c | #7fce9f / #e59a9a | **régime risk-on/off** (outline désaturé, `.badge-regime`) |
| `--warn` | #d97706 | #f59e0b | avertissements, cycle « slowdown » |

**Règle couleur non négociable** : `--pos`/`--neg` = P&L (gain/perte) uniquement, traitement plein.
Le régime (risk-on/off) utilise `--regime-on`/`--regime-off` — vert/rouge **désaturés en outline**, jamais le même
traitement que le P&L. Cycle macro : `expansion→regime-on · recovery→accent · slowdown→warn · recession→regime-off`.

## Typo / espacement / rayons
- Police : `-apple-system / SF Pro Text / Inter`. Mono : `SF Mono / JetBrains Mono` (`.mono`).
- **Chiffres tabulaires partout** : `tbody td` porte `font-variant-numeric:tabular-nums` par défaut ;
  utilitaires `.mono`, `.display`, `.tnum` pour le hors-tableau. Alignement financier garanti.
- Espacement multiples de 4px. Rayons : 8 / 12 / 16px.

## Composants (réels)
- **Charts** : `EquityChart` + `DrawdownChart` (**Recharts**, axes X synchronisés via `syncId`,
  downsampling LTTB ~600 pts recalculé au zoom pour le 60 fps) ; `TechnicalChart` + crypto (**lightweight-charts**,
  TradingView) ; `VixPlaybook` (Recharts) ; `CorrelationHeatmap` (cellules colorées maison).
- **KPI / tables** : `MetricCard` (count-up + delta discret), `SortableTable` (tri/filtre/CSV — **fait main**,
  pas de `@tanstack/react-table`), `RegimeBanner`, `SentimentBanner`.
- ⚠️ Pas de shadcn/ui, pas de Radix, pas de visx dans le code réel (contrairement aux anciennes notes).

## Écrans
Dashboard (✅ refonte BLOC 5 : grille régime→KPIs→equity+underwater→positions/alertes) · Screener · Universe ·
Macro · Crypto · Portfolio · Risk · Positions · Trades · Live · Notes · Conviction · Échecs · Méthode.

## Animations (discipline)
Transitions d'état 150-250ms ease-out · stagger cartes 30-50ms · skeletons/`shimmer` au chargement · hover states.
`prefers-reduced-motion` coupe tout (règle globale). **INTERDIT** : parallax, boucles, mouvement sans fonction.
Le décor animé global (aurora/ken-burns/halos/grille/particules) est **neutralisé sur `/dashboard`** (route sobre).

## Accessibilité & perf
Contraste AA · navigation clavier (`:focus-visible`) · responsive mobile-first (PWA) · skeletons · 60 fps
(charts `memo` + downsampling, `isAnimationActive={false}`). Site statique : JSON NaN-safe (`dump_static.py::_clean`).
