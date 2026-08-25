# Audit du projet — Quant Terminal

> Audit réalisé le **2026-08-25** sur `main` (`c564177` + travaux de finalisation).
> Méthode : inspection intégrale du dépôt, exécution réelle de la suite de tests, lecture du
> chemin d'exécution de production. Aucun chiffre de ce document n'est estimé : ce qui n'a pas
> été mesuré est marqué **NON MESURÉ**.

---

## 1. Architecture réelle

Le dépôt est un monorepo Python + Next.js. Il n'y a **pas** de service permanent : tout part
d'un `snapshot` recalculé, servi par une API FastAPI locale et consommé par un front statique.

```
                          data/  (YAHOO.db, market.db, crypto.db — LOCAL, jamais commité)
                            │
                  packages/data  ── providers, audit d'intégrité, contrats OHLCV
                            │
        ┌───────────────────┼────────────────────┐
        ▼                   ▼                    ▼
 packages/screening   packages/backtest    packages/fundamentals
 packages/indicators  packages/portfolio   packages/macro
 packages/regime      packages/research    packages/sentiment
        │                   │                    │
        └───────────────────┼────────────────────┘
                            ▼
                   apps/api/snapshot.py        ← assemble TOUT le payload
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
      apps/api/main.py (FastAPI)   scripts/dump_static.py → apps/web (Next.js)
              │
              ▼
      scripts/run_live.py  ── SEUL chemin qui envoie des ordres
              │
              ▼
      packages/risk/order_gate.py  ← portail pré-trade (ajouté le 25/08)
              │
              ▼
      packages/execution/{alpaca,binance,bitmart}_broker.py
```

### Flux IA — et sa séparation

```
packages/llm  ──►  apps/api/main.py  (endpoints /api/ai/*)  ──►  TEXTE affiché
                                                                       │
                                                                       ✗
                                             aucun chemin vers un ordre
```

**Vérifié par inspection des imports** : `packages.llm` n'est importé que par `apps/api/main.py`,
et uniquement pour des endpoints de génération de texte. Aucun module d'exécution, de stratégie
ou de risque ne l'importe. L'IA ne peut pas contourner le risk management parce qu'elle n'est
pas dans la chaîne du tout.

`packages/intelligence` (ajouté le 25/08) hérite de la même contrainte, garantie cette fois par
un **test qui inspecte l'arbre syntaxique** : `tests/intelligence/test_intelligence.py::
test_la_couche_intelligence_ne_peut_pas_atteindre_un_courtier`.

---

## 2. État de chaque module

| Module | Lignes | État | Remarques |
|---|---:|---|---|
| `data` | 3322 | **STABLE** | Deux schémas de base lus (LONG + normalisé). Audit PwC + contrats OHLCV en CI. |
| `research` | 2672 | **STABLE** | Ledger anti p-hacking, DSR, PBO/CSCV, gate 4 étages, attribution alpha/bêta. |
| `portfolio` | 2646 | **STABLE** | TWR (GIPS), ERC, PSR/DSR, réplication modèle↔réel. |
| `reporting` | 2595 | **STABLE** | Notes institutionnelles, tear sheets. Dépendance optionnelle `reportlab`. |
| `backtest` | 2508 | **NEEDS_IMPROVEMENT** | Fenêtre de panel corrigée le 25/08 ; **13 autres sites `min(len)` non migrés**. |
| `execution` | 2225 | **NEEDS_IMPROVEMENT** | `impact.py` et `almgren_chriss.py` écrits, testés, **jamais exécutés sur données réelles**. |
| `fundamentals` | 1182 | **STABLE** | Vernimmen/Damodaran, plafond de croissance perpétuelle, ROCE après impôt. |
| `mcp_tradingview` | 1133 | **STABLE** | Couvert le 25/08 : le filtre d'âge des alertes était inerte (veto permanent) et une sévérité inconnue était dégradée en `info`. Corrigés. |
| `ml` | 1109 | **EXPERIMENTAL** | Walk-forward point-in-time correct ; `sklearn` optionnel. |
| `storage` | 891 | **STABLE** | Journal SQLite, `safe_pickle` (anti-symlink + hash). |
| `screening` | 816 | **STABLE** | |
| `regime` | 810 | **STABLE** | |
| `intelligence` | 626 | **INCOMPLETE** | Architecture + scoring **complets et testés** ; **aucun collecteur** (pas d'accès X/news). |
| `risk` | 518 | **NEEDS_IMPROVEMENT** | Portail pré-trade branché le 25/08. `RiskEngine` reste hors du chemin de production. |
| `strategies` | 457 | **STABLE** | Plugins auto-enregistrés. |
| `profile` | 353 | **STABLE** | Capacité/tolérance, allocation stratégique, tilts bornés par la preuve. |
| `llm` | 296 | **STABLE** | Multi-fournisseur, diagnostic explicite, `guard_numbers`. |
| `macro` | 164 | **NEEDS_IMPROVEMENT** | Détection de péremption OK ; séries additionnelles (NFCI, ICSA…) non branchées. |
| `testing` | 75 | **EXPERIMENTAL** | Aucun fichier de test dédié. |

---

## 3. Risques techniques

| # | Risque | Gravité | État |
|---|---|---|---|
| T1 | ~~13 sites `min(len(data[s]))` non migrés~~ | ÉLEVÉ | **fermé le 25/08** — 0 site restant |
| T2 | `RiskEngine` (règles reward/risk, stops) hors du chemin de production | MOYEN | partiellement couvert par `order_gate` |
| T3 | ~~`mcp_tradingview` sous-testé~~ | MOYEN | **fermé le 25/08** — 2 défauts actifs trouvés et corrigés |
| T4 | Modules d'exécution avancés jamais exécutés sur données réelles | MOYEN | ouvert |
| T5 | ~~Couverture non mesurée~~ | FAIBLE | **fermé le 25/08 — 81 %**. Reste `regime/real_macro.py` à 0 % (53 l., alimente la porte de régime) |
| T6 | `apps/web/app/dashboard/page.tsx` à 435 lignes (limite projet : 400) | FAIBLE | ouvert |
| T7 | `make lint` échoue : 4333 erreurs ruff dont 3847 `E501` — la CI l'exécute en **non bloquant** | FAIBLE | préexistant, assumé |

**T1 est fermé.** Les 13 sites ont été migrés. L'audit site par site a révélé que le problème
n'était pas uniforme :

- **7 sites** portaient bien le défaut (`conviction_backtest` ×2, `megacap` ×2, `crypto_sleeve`,
  `sector_momentum`, `weighting_backtest`, `ml_walkforward`) → migrés vers `fenetre_commune`.
- **3 sites** de `preset_backtest` n'étaient PAS le défaut : le bloc `_lens`/`_need` qui les
  précédait implémentait déjà une fenêtre commune, par RANG au lieu de par couverture, et ce
  compromis profondeur/largeur était délibéré. Extraits dans `panel.fenetre_par_rang`, sémantique
  inchangée — la triplication était la dette, pas la règle.
- **1 site** était du calcul mort (`L` et `M` écrasés quatre lignes plus bas) → supprimé.
- **1 site** était un défaut que le raisonnement seul ne voyait pas : `preset_latest_weights`
  semblait à l'abri puisque tout y est ancré sur la fin de la série. **Mesure : une seule série de
  125 barres, incapable d'entrer dans le top-12, déplaçait les poids envoyés au courtier de
  2 points.** Cause : `_regime_mult` lit `hist[-200:]` et le pic historique — sur un panel tronqué
  la « MM200 » devient une MM125. Corrigé, et le seuil d'éligibilité passe à 200 barres
  (`MIN_BARRES_REGIME`).

---

## 4. Risques trading

| Domaine | Risque identifié | État |
|---|---|---|
| **Marché** | maxDD réel du preset mesuré à **−19,4 %** sur 126 rebalancements (contre −5,1 % affiché sur un panel tronqué à 7 pas) | **mesuré le 25/08** |
| **Données** | mode « mixte » : 788 séries réelles sur 929 — le reste est en repli. Les symboles synthétiques sont exclus de l'allocation. | contrôlé |
| **Backtesting** | biais du survivant **mesurable** depuis le 25/08 (`aligner_dates=True`). Le chiffre obtenu est un **MINORANT** : une ligne radiée est soldée à son dernier cours coté, qui surestime la récupération d'une faillite. | **à mesurer sur données réelles** |
| **Backtesting** | fondamentaux **non point-in-time** : le score du jour est appliqué à des dates passées en production (légitime) mais l'univers de backtest est sélectionné par momentum prix-only pour l'éviter | contrôlé |
| **Données** | ~~calendriers mêlés~~ : l'empilement positionnel superposait une colonne crypto de 2018 à une colonne action de 2015 (**3 ans d'écart**), ce qui plaçait 12 paires crypto dans le top-30 par artefact | **corrigé le 25/08** |
| **Backtesting** | `preset_equity_daily` / `trade_log` / `ledger` calculent encore leurs rendements par empilement positionnel : leur courbe peut diverger du tableau | **ouvert — P0** |
| **Signaux** | `k_signal` médian = **1** sur 126 rebalancements : l'optimisation transversale (ERC) répartit du risque sur une matrice à une seule direction fiable | **ouvert** |
| **Signaux** | deux garde-fous réagissaient à l'artefact de calendrier : la cible de vol bridait **89 %** des pas (×0,743) et la porte de régime coupait **73 %** de l'exposition, parce que l'indice de marché et la covariance étaient dominés par 12 paires crypto. Après correction : 7 % (×0,990) et ×0,697. | **corrigé le 25/08** |
| **Signaux** | les 5 hypothèses d'alpha sont rejetées en long/short et « promues » en long-only — écart imputable au bêta, désormais mesuré | corrigé le 25/08 |
| **Position sizing** | plancher de ligne 1 000 $ + bande d'inaction 3 % ; la bande bloque **99 % des pas** et ne laisse trader que ~7 % des noms | **à instruire** |
| **Exécution** | kill-switch TradingView : une alerte critique périmée vetoait **à vie** (filtre d'âge déclaré, jamais appliqué) | **corrigé le 25/08** |
| **Exécution** | ~~`exec_lag=0`, mini look-ahead~~ : `exec_lag=1` (fill t+1, réaliste) est le défaut depuis le 25/08 — meilleur sur toutes les colonnes une fois l'alignement en place | **corrigé** |
| **API** | equity illisible ⇒ broker écarté (`vet_brokers`) ; inconnu ≠ zéro | contrôlé |
| **Levier** | `QUANT_RISK_MAX_GROSS = 1.00` — aucun levier possible via le portail | contrôlé |
| **Drawdown** | kill-switch DD réel intraday + kill-switch alertes TradingView | contrôlé |

---

## 5. Dette technique

1. Migrer les 13 sites `min(len)` restants (**P0**).
2. Ingérer des délistés qui auraient été **sélectionnés** — sinon le test de survivant ne mesure rien (**P0**).
3. Brancher `RiskEngine` (stops, reward/risk) sur le chemin de production, ou le supprimer (**P1**).
4. Couvrir `mcp_tradingview` : il pilote un kill-switch (**P1**).
5. Instruire la bande d'inaction : 3 % en poids absolu ≈ une position entière à 30 noms (**P1**).
6. Exécuter `impact.py` / `almgren_chriss.py` sur données réelles ou les marquer EXPERIMENTAL (**P2**).
7. Installer `pytest-cov` et publier une couverture réelle (**P2**).
8. Trancher la contradiction de lint : `pyproject.toml` fixe `line-length = 88`, le dépôt écrit
   autour de 100. Aligner la configuration sur l'usage, ou reformater — mais ne pas laisser les
   deux se contredire (**P2**).
8. Découper `apps/web/app/dashboard/page.tsx` (**P3**).

---

## 6. Ce que cet audit n'a PAS pu établir

- ~~La couverture de tests~~ — **mesurée : 81 %** (`make coverage`).
- **La validité des chiffres publiés par les 13 modules non migrés.**
- **L'ampleur du biais du survivant sur les données RÉELLES.** Le moteur sait maintenant la
  mesurer (`make preset-lab`, ligne « +alignement par date »), mais aucun chiffre réel n'a encore
  été produit — et il ne sera qu'un minorant.
- **Le comportement réel des brokers** : aucun ordre n'a été envoyé pendant cet audit, conformément
  à la consigne. Le câblage du portail de risque est vérifié par des courtiers factices
  (`tests/execution/test_run_live_risk_gate.py`), pas contre une API réelle.
