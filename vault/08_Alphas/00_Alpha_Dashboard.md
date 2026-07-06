---
type: alpha_dashboard
---

# 📊 Tableau de bord des hypothèses d'alpha

> Pipeline de recherche **requêtable** : chaque note d'hypothèse (`08_Alphas/`) a un frontmatter
> `statut/facteur/classe/horizon/dsr/pbo`. Ce tableau se met à jour seul (plugin **Dataview**, gratuit).
> Règle d'or : aucun facteur n'est **promu** sans `dsr > 0.5` ET `pbo < 0.5`.

## Toutes les hypothèses (triées par DSR)
```dataview
TABLE statut, facteur, classe, horizon, dsr, pbo, maxdd
FROM "08_Alphas"
WHERE type = "alpha_hypothesis"
SORT dsr DESC
```

## En test (à arbitrer)
```dataview
TABLE facteur, classe, these
FROM "08_Alphas"
WHERE type = "alpha_hypothesis" AND statut = "en_test"
```

## Promus mais DSR≈0 (honnêteté : gérés comme risque, pas comme alpha)
```dataview
TABLE facteur, dsr, maxdd
FROM "08_Alphas"
WHERE type = "alpha_hypothesis" AND statut = "promu" AND dsr <= 0.5
```

---
**Ledger d'essais** (anti p-hacking) : `research/hypotheses.jsonl` — chaque calibration loguée via
`make log-alpha`. Le nombre d'essais `N` déflate le seuil DSR (López de Prado). Voir aussi
`packages/research/ledger.py` (`trial_count`, `summary`, `best_by_dsr`).

## Liens directs (graphe & backlinks — en plus de Dataview)
Hypothèses : [[momentum_12_1]] · [[trend_ma200]] · [[low_vol]] · [[quality]] · [[value_multiples]] ·
[[pead]] · [[overnight]] · [[ts_momentum]] · [[insider_form4]]
Backtests & verdicts de gate : [[PEAD_smid]] · [[Regime_FearGreed]]
Références : [[paper_jegadeesh_titman_1993]] · [[paper_moskowitz_tsmom_2012]] ·
[[paper_bernard_thomas_1989]] · [[paper_cooper_overnight]] · [[paper_lakonishok_lee_2001]]
