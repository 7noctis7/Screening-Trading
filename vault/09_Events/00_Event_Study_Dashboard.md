---
type: event_dashboard
---

# 🛰️ Recherche event-driven — tableau de bord

> Pipeline (ordre NON négociable) : **event-store point-in-time** → **event-study (CAR + placebo)**
> → LLM en extraction seule → ML (triple-barrier + PurgedKFold) → gate DSR/PBO → ledger.
> On ne code le ML/LLM **que si** l'event-study est significatif (p<0.05 vs placebo).

## Briques (code)
- `packages/research/event_store.py` — Event PIT (`ts_public`), dédup, ontologie légère (Karp).
- `packages/research/feature_store.py` — jointure **as-of** (anti look-ahead, Ghodsi) ; DuckDB `ASOF JOIN` à l'échelle.
- `packages/research/event_study.py` — CAR + **placebo** (dit si un lien existe AVANT tout ML).

## Études d'events (à remplir au fil des runs — auto-note par event-study)
```dataview
TABLE event_type, n, mean_car, t_stat, placebo_p_value, significant
FROM "09_Events"
WHERE type = "event_study_result"
SORT significant DESC, placebo_p_value ASC
```

## Garde-fous (Assassin + Gardien)
- `ts_public` = instant public (jamais la survenance). Mapping ticker **point-in-time**.
- Features ≤ `ts_public` ; labels triple-barrier = futur (étiquette seulement).
- LLM : corpus **as-of**, extraction uniquement, sous `guard` anti-hallucination.
- Multiple testing → déflation via le ledger `N`. Significatif vs **placebo**, pas en absolu.

## Vérité (Arbitre)
Le **moat = l'event-store point-in-time auditable**, pas le LLM. Géopolitique Osiris = mirage
pour le daily (pas d'historique PIT). Sources retenues : SEC EDGAR (Form 4/8-K, `ts_public` propre).
