# Rapport de tests — 2026-08-25

> Tous les chiffres ci-dessous proviennent d'exécutions **réelles** de la suite, dans
> l'environnement de développement du dépôt. Aucun résultat n'est reporté sans avoir été observé.

## Commande et résultat

```
$ python3 -m pytest -q
1251 passed, 8 skipped, 2 warnings in 173.52s
```

| Mesure | Valeur |
|---|---:|
| Tests collectés | 1 259 |
| **Réussis** | **1 251** |
| Échecs | **0** |
| Ignorés | 8 |
| Durée | 2 min 54 s |

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
| `tests/backtest/test_panel_window.py` | 13 | Une série courte ne tronque plus le panel ; compteurs de garde-fous ; **les poids de PRODUCTION sont insensibles à une série courte** (mesuré : 2 points d'écart avant correctif). |
| `tests/research/test_attribution.py` | 6 | Un levier pur (1,5× le benchmark) doit être refusé comme candidat. |
| `tests/portfolio/test_replication.py` | 10 | L'écart de réplication ne peut pas descendre sous la poche hors modèle. |
| `tests/data/test_engine_schema_normalise.py` | 4 | Les deux schémas de base sont lus. |
| `tests/execution/test_ibkr_demo_only.py` | 21 | IBKR ne peut pas atteindre un compte réel : port, identifiant de compte, opt-in — et **aucun argument n'ouvre le réel** (vérifié par introspection de la signature). |
| `tests/mcp_tradingview/test_alerts_kill_switch.py` | 26 | Le filtre d'âge des alertes existe vraiment ; une sévérité inconnue vaut `warning`, jamais `info` ; une alerte non datable est conservée mais signalée. |
| `tests/backtest/test_alignement_par_date.py` | 11 | Sur calendrier uniforme, l'alignement par date donne des courbes **identiques au bit près** — c'est la propriété qui rend la migration sûre. Un délisté a des NaN, jamais des zéros. |
| `tests/backtest/test_survivorship_validity.py` | 8 | Le test de biais du survivant dit quand il ne mesure rien, au lieu de renvoyer 0. |

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

## Couverture : **81 %** — mesurée le 25/08

```
$ make coverage
TOTAL   15632 lignes   2983 non couvertes   81%
```

`pytest-cov` a finalement pu être installé (PyPI est autorisé par le proxy). Le chiffre était
publié comme « NON MESURÉ » — il ne l'est plus.

### Où sont les trous, et lesquels comptent

La majorité des modules faiblement couverts sont des **adaptateurs réseau** (yfinance, SEC, RSS,
IMF, SDK courtiers) : leurs lignes non couvertes sont les appels HTTP eux-mêmes. C'est attendu
et défendable.

Deux exceptions méritaient un examen, toutes deux à **0 %** :

| Module | Avant | Après | Pourquoi ça comptait |
|---|---:|---:|---|
| `packages/data/fx.py` | 0 % | **80 %** | Convertit les comptes d'un ADR vers la devise de son cours. Un taux faux ne lève rien : il produit un P/E, un DCF et une marge de sécurité crédibles et **erronés**. Écrire les tests a révélé un défaut réel (cf. ci-dessous). |
| `packages/regime/real_macro.py` | 0 % | 0 % | **Toujours ouvert.** Alimente la porte de régime, qui pilote l'exposition. 53 lignes sans un seul test. |

### Le défaut trouvé en écrivant les tests de `fx.py`

Le TTL de cache portait sur le **fichier**, pas sur l'entrée. Comme `_save` réécrit tout le
fichier, récupérer une paire quelconque remettait le compteur de fraîcheur à zéro pour **toutes**
les autres : une paire peu utilisée (TWD, JPY) pouvait être servie indéfiniment avec un taux de
plusieurs mois. Le code ne stockait aucun horodatage par entrée — il ne *pouvait* donc pas
distinguer un taux d'une minute d'un taux d'un semestre.

Chaque entrée porte désormais sa date, `age_heures()` la rend lisible, et l'ancien format
(valeur nue, sans date) est traité comme périmé plutôt que présumé frais.

## Problèmes restant ouverts

1. ~~13 sites `min(len)` non migrés~~ — **fermé**, 0 site restant.
2. ~~`mcp_tradingview` sous-testé~~ — **fermé**. Écrire les tests a révélé deux défauts actifs
   sur le chemin du kill-switch (filtre d'âge inerte, sévérité inconnue dégradée en `info`).
3. **`packages/testing`** : aucun test dédié.
3 bis. **`packages/regime/real_macro.py` à 0 %** : 53 lignes non testées sur un module qui
   alimente la porte de régime, donc l'exposition. Même famille que `mcp_tradingview`.
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
