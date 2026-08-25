# Rapport de tests — 2026-08-25

> Tous les chiffres ci-dessous proviennent d'exécutions **réelles** de la suite, dans
> l'environnement de développement du dépôt. Aucun résultat n'est reporté sans avoir été observé.

## Commande et résultat

```
$ python3 -m pytest -q
1165 passed, 8 skipped, 2 warnings in 222.57s
```

| Mesure | Valeur |
|---|---:|
| Tests collectés | 1 173 |
| **Réussis** | **1 165** |
| Échecs | **0** |
| Ignorés | 8 |
| Durée | 3 min 42 s |

## Les 8 tests ignorés — et pourquoi

Aucun n'est un test désactivé pour masquer un problème. Les huit le sont par **dépendance
optionnelle absente** de cet environnement minimal :

| Test | Dépendance manquante |
|---|---|
| `tests/data/test_hf_analytics.py` | `duckdb` |
| `tests/execution/test_alpaca_crypto.py` | `alpaca-py` (couvert en CI) |
| `tests/property/test_math_invariants.py` | `hypothesis` |
| `tests/universe/test_wikipedia_parser.py` | `lxml` |
| `tests/ml/test_model_eval_gov.py` | `sklearn` |
| `tests/portfolio/test_vol_managed.py` | `skfolio` |
| `tests/reporting/test_company_report.py` | `reportlab` |
| `tests/reporting/test_tearsheet.py` | `reportlab` |

Recherche de tests volontairement neutralisés : **une seule occurrence** de `skipif` dans tout
`tests/`, celle de `skfolio` ci-dessus. Aucun `xfail`, aucun test commenté.

## Tests ajoutés pendant cette mission

| Fichier | Tests | Ce qu'ils protègent |
|---|---:|---|
| `tests/execution/test_run_live_risk_gate.py` | 5 | Le portail est réellement CÂBLÉ dans le chemin d'ordres — une règle correcte mais non branchée ne protège rien. |
| `tests/risk/test_order_gate.py` | 18 | Le portail ne peut que réduire ; un désengagement n'est jamais bloqué ; inconnu ≠ zéro ; limites illisibles → défaut. |
| `tests/intelligence/test_intelligence.py` | 25 | Une opinion ne devient jamais un fait ; les échos ne sont pas des confirmations ; 5 M d'abonnés ne battent pas une source officielle ; la couche ne peut pas importer l'exécution. |
| `tests/backtest/test_panel_window.py` | 8 | Une série courte ne tronque plus le panel ; compteurs de garde-fous. |
| `tests/research/test_attribution.py` | 6 | Un levier pur (1,5× le benchmark) doit être refusé comme candidat. |
| `tests/portfolio/test_replication.py` | 10 | L'écart de réplication ne peut pas descendre sous la poche hors modèle. |
| `tests/data/test_engine_schema_normalise.py` | 4 | Les deux schémas de base sont lus. |

## Couverture des composants critiques

| Composant | Fichiers de test | État |
|---|---|---|
| Calcul PnL / TWR | `tests/portfolio/test_twr.py`, `tests/api/*` | couvert |
| Frais / slippage | `tests/execution/test_costs.py`, `test_tca.py` | couvert |
| Position sizing | `tests/execution/test_rebalance_plan.py`, `tests/risk/test_order_gate.py` | couvert |
| Exposition max / levier | `tests/risk/test_order_gate.py` | couvert |
| Drawdown / kill-switch | `tests/execution/test_live_guards.py`, `tests/risk/*` | couvert |
| Limites portefeuille | `tests/risk/test_limits.py`, `tests/portfolio/test_risk_budget.py` | couvert |
| Ordres / positions | `tests/execution/test_sim_broker_idempotent.py`, `test_reconcile.py` | couvert |
| Erreurs API / reconnexion | `tests/common/test_retry.py`, `tests/execution/test_live_guards.py` | couvert |
| Fills partiels | `tests/execution/test_reconciliation.py` | couvert |
| Stop loss / take profit | `tests/risk/test_risk.py`, `tests/portfolio/test_sizing.py` | **partiel** — 3 tests seulement dans `test_risk.py` |
| Anti-fuite backtest | `tests/backtest/test_dashboard_no_leak.py`, `test_ml_walkforward.py` | couvert |
| Synchronisation broker | `tests/execution/test_reconcile.py` | couvert |

## Couverture chiffrée : NON MESURÉE

`pytest-cov` n'est pas installé dans cet environnement et n'a pas pu l'être. **Aucun pourcentage
de couverture n'est publié** : en inventer un serait précisément le genre d'affirmation que ce
rapport existe pour éviter.

Pour l'obtenir : `pip install pytest-cov && pytest --cov=packages --cov-report=term-missing`.

## Problèmes restant ouverts

1. **13 sites `min(len)` non migrés** — leurs chiffres restent suspects. Aucun test ne les couvre
   aujourd'hui sur ce point précis.
2. **`mcp_tradingview`** : 7 modules, 2 fichiers de test, et il pilote un kill-switch.
3. **`packages/testing`** : aucun test dédié.
4. Le test de biais du survivant **s'exécute et ne mesure rien** (les délistés ingérés n'entrent
   jamais dans le top-30). Il passe — ce n'est pas la même chose que « il valide quelque chose ».

## Lint — état réel

```
$ ruff check packages apps
Found 4333 errors.   (3847 = E501 line-too-long)
```

`make lint` **ne passe pas**, et ne passait pas avant cette mission. La CI l'exécute
explicitement en mode **non bloquant** (`.github/workflows/ci.yml` : « ruff check (non
bloquant) », « mypy (non bloquant — strict trop bruyant sur le legacy) »). C'est donc un état
connu et assumé, pas une régression.

**89 % des erreurs sont `E501`** : `pyproject.toml` fixe `line-length = 88` alors que le dépôt
écrit de fait autour de 100 caractères. Les deux options honnêtes sont d'aligner la configuration
sur l'usage, ou de reformater le dépôt — pas de laisser les deux se contredire indéfiniment.

Les fichiers ajoutés pendant cette mission ne contiennent **plus aucune erreur autre que E501**
(sémicolons, imports non triés, `str`+`Enum` obsolète et nom de variable ambigu corrigés).
