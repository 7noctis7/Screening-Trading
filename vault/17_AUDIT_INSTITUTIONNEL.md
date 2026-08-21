# 17 — AUDIT INSTITUTIONNEL & PLAN D'ENRICHISSEMENT (2026-08-20)

> Audit du dépôt à l'aune du corpus Grinold-Kahn / Isichenko / Paleologo / Chan / Taleb /
> Mandelbrot / Wilmott. **Rien ici n'est un résultat mesuré** : ce sont des spécifications
> et des findings de CODE (chemins de fichiers vérifiés). Tout chiffre de performance
> reste soumis au gate `packages/research/gate.py` et au mandat données-réelles.

Détail par axe : [[AXE1_DATA_PIT]] · [[AXE2_ALPHA_LOI_FONDAMENTALE]] · [[AXE3_QUEUES_REGIMES]]
· [[AXE4_SIZING_FRICTIONS]] · [[AXE5_EXECUTION]] (dossier `vault/17_UPGRADE/`).

---

## 0. Verdict en trois lignes

1. **Le socle recherche-intégrité est au niveau institutionnel** (gate 4 étages, ledger,
   PIT macro, CV purgée, journal persistant, sabotage) — c'est rare et c'est l'actif principal.
2. **Trois couches sont en dessous du niveau annoncé** : le stockage des prix n'est pas
   point-in-time (ajustement écrasé en place), la loi fondamentale n'est mesurée nulle part
   (ni IC, ni souffle effectif, ni coefficient de transfert), et le modèle de coût est un
   forfait linéaire — inutilisable pour arbitrer les horizons 1 h / 4 h.
3. **Les robots 1 h / 4 h n'ont aujourd'hui aucun substrat de données** (`bars_repo` porte
   la colonne `timeframe`, aucun ingest intraday n'existe). Avant d'écrire une ligne de robot
   horaire, l'arithmétique de l'axe 4 § 4.5 doit être refaite avec TES coûts : sur actions US
   au tarif retail, elle conclut à la non-viabilité ; sur crypto perp, elle passe.

---

## 1. Tableau de bord de l'audit

| Bloc théorique | Ce qui existe (vérifié) | Trou principal | Priorité |
|---|---|---|---|
| PIT fondamental/macro (Isichenko) | `packages/common/pit_guard.py`, vintages ALFRED, `stable_prefix` | Garde *fonctionnelle*, pas *structurelle* : aucun schéma bitemporel ne rend la fuite impossible | **P0** |
| PIT prix / corporate actions | `auto_adjust=True` + `_split_drift` (re-backfill) | L'historique **mute** à chaque split/dividende → backtests non reproductibles, niveaux de prix contaminés | **P0** |
| Biais du survivant | `data/survivorship.py`, `survivorship_delta.py`, `delisted.csv` | Pas de prix des délistés, pas d'ID permanent, pas de rendement de radiation | **P0** |
| Loi fondamentale (Grinold) | `alpha_decay.ic_half_life`, z-scores dans `ranking/engine.py` | IC jamais converti en alpha ; BR compté naïvement ; TC jamais mesuré | **P1** |
| Orthogonalisation (Paleologo) | `sector_neutral` (démoyennage), `factor_risk.pca_risk` | Aucune neutralisation par projection sur les loadings ; alpha = bêta déguisé non mesuré | **P1** |
| Queues épaisses (Mandelbrot/Taleb) | `evt.py` (POT/GPD), `risk_metrics` CVaR, `garch.py`, `fragility.py` | Estimateur GPD par moments (biaisé si ξ≥0,5) ; **indice de queue α jamais estimé** ; bootstrap Sharpe i.i.d. | **P1** |
| Régimes (Wilmott) | `vol_regime.py` (terciles + HMM 2 états), `_regime_mult` | Terciles et HMM ajustés sur **tout** l'échantillon → inutilisables en backtest en l'état | **P1** |
| Cointégration (Chan) | *rien* (`grep coint\|adf\|johansen` = 0 résultat avant cette session) | Module livré ici : `packages/research/cointegration.py` | **P1** |
| Frictions (Chan/Iqbal) | `costs.py` (bps fixes), `tca.py`, `exec_costs.py` (slippage réel) | Coût **linéaire** : aveugle à la taille, à l'ADV et à la vol → surestime tout robot rapide | **P0** |
| Sizing (Kelly) | `sizing/kelly_uncertain.py` (Kelly binomial + shrinkage) | Deux issues seulement, pas de queue GPD, fraction 0,25 non dérivée d'un budget de DD → module livré ici | **P1** |
| Exécution / LOB | `SimBroker` (fill immédiat au prix courant ± bps) | Aucune file d'attente, aucun fill partiel, `exec_lag` par défaut = 0 | **P0 avant intraday** |
| Disjoncteurs | `dd_kill_switch`, `live_guards`, `alerts`, `reconcile`, idempotence | Pas de **dead-man switch**, pas de machine à états de dégradation, pas de disjoncteur de slippage | **P0-SI-LIVE** |

---

## 2. Findings de code (chemin + ligne, reproductibles)

| # | Sévérité | Fichier | Constat |
|---|---|---|---|
| F1 | **HAUTE** | `scripts/ingest_prices.py:92` + `:138` | `auto_adjust=True` écrit des OHLC **rétro-ajustés** ; `_split_drift` déclenche un re-backfill → la série passée change après coup. Toute comparaison DSR/PBO entre deux dates de run compare des historiques différents, et `stable_prefix` échouerait par construction sur les prix. Correctif : cf. [[AXE1_DATA_PIT]] § 2. |
| F2 | **HAUTE** | `packages/execution/costs.py` | Coût = bps constants. Un ordre de 0,1 % d'ADV et un ordre de 20 % d'ADV paient le même prix. Conséquence directe : `preset_backtest` (ligne `cost = Σ|w−w_prev|·rt`) sous-estime le coût des grosses rotations et sur-estime celui des petites → le classement des configs de `make preset-lab` est biaisé. Correctif : `packages/execution/impact.py` (livré). |
| F3 | **HAUTE** | `packages/regime/vol_regime.py:52` | `np.percentile(valid, [33,66])` et `GaussianHMM(...).fit(x)` sont calculés sur **tout** l'échantillon, futur inclus. Aujourd'hui appelé uniquement depuis `apps/api/snapshot.py` (affichage/live) → **pas** de fuite en production, mais tout câblage dans une boucle de backtest en injecterait une. Correctif : fenêtre expansive + probabilité **filtrée**, cf. [[AXE3_QUEUES_REGIMES]] § 3. |
| F4 | MOYENNE | `packages/backtest/preset_backtest.py:~215` (`exec_lag`) | `exec_lag` par défaut = 0 : signal calculé au close t, exécuté au close t. Le défaut devrait être 1 ; 0 doit rester une option de non-régression explicitement étiquetée « optimiste ». |
| F5 | MOYENNE | `packages/portfolio/psr.py` (`bootstrap_sharpe_ci`) | Rééchantillonnage **i.i.d.** alors que le front (`components/Simulator.tsx`) utilise un bootstrap par **blocs** de 10 j. Sous clustering de volatilité, l'IC i.i.d. est trop étroit → le backend est plus optimiste que le front sur la même courbe. Aligner sur un bootstrap stationnaire (Politis-Romano). |
| F6 | MOYENNE | `packages/ranking/engine.py:35` (`_zscore`) | z-score moyenne/écart-type sans winsorisation, sur des distributions à queues épaisses : un seul outlier déplace `mu` et écrase le classement. De plus le démoyennage sectoriel s'applique à des groupes de taille quelconque (un secteur à 2 noms produit mécaniquement ±1). Correctif : z robuste (médiane/MAD) + winsorisation ±3 + taille de groupe minimale, cf. [[AXE2_ALPHA_LOI_FONDAMENTALE]] § 1. |
| F7 | MOYENNE | `packages/portfolio/evt.py:fit_pot` | GPD estimée par **méthode des moments** : incohérente dès ξ ≥ 0,5 (variance des excès infinie) — précisément le régime crypto. Correctif : moments pondérés par les probabilités (PWM), formules fermées vérifiées dans [[AXE3_QUEUES_REGIMES]] § 1. |
| F8 | MOYENNE | `packages/backtest/preset_backtest.py` (`band`) | Bande de non-trading en dur, sans lien avec le rapport coût/alpha. Forme théorique disponible : `impact.no_trade_band` (racine cubique). |
| F10 | MOYENNE | `packages/portfolio/sizing/kelly_uncertain.py` + `QUANT_DD_TARGET` | Deux expressions contradictoires du même appétit pour le risque : `fraction=0.25` correspond à un budget de drawdown de **50 %** (à 1 % de probabilité), alors que `QUANT_DD_TARGET=0.25` en vise **25 %**, ce qui impose `lambda ≈ 0,175`. Dérivation et table dans [[AXE4_SIZING_FRICTIONS]] § 1. |
| F9 | BASSE | univers `data/universe/wikipedia_source.py` | La composition d'indice est lue **au présent** : un backtest 2015 utilise les membres de 2026 (biais du survivant + look-ahead d'inclusion). Le correctif P0-1 (sélection par momentum prix-only) réduit le symptôme sans traiter la cause : il manque une table `index_membership` datée. |

---

## 3. Ce qui a été livré dans cette session (code, testé)

| Module | Rôle | Tests |
|---|---|---|
| `packages/research/breadth.py` | Souffle **effectif** (N_eff, T_eff), coefficient de transfert TC, IR = IC·√BR·TC, alpha de Grinold, décroissance d'IC | `tests/research/test_breadth.py` (7) |
| `packages/execution/impact.py` | Impact en **racine carrée** (Almgren/Torre), vol et volume de la **fenêtre** d'exécution, taille max sous budget de coût, plafond de participation, **test d'admission** alpha vs coût, bande de non-trading | `tests/execution/test_impact.py` (7) |
| `packages/research/cointegration.py` | ADF (valeurs critiques **Engle-Granger**, pas ADF standard), ratio de couverture, demi-vie OU, z glissant, correction multi-tests, verdict de paire bidirectionnel | `tests/research/test_cointegration.py` (10) |
| `packages/portfolio/sizing/kelly_fat_tail.py` | Kelly sur distribution **empirique + queue GPD**, borne de ruine, et fraction `lambda` **dérivée d'un budget de drawdown** (`lambda = 2/(1 + ln eps / ln b)`) au lieu d'être posée à 0,25 | `tests/portfolio/test_kelly_fat_tail.py` (7) |

Suite verte sur le périmètre touché : `pytest tests/research tests/execution tests/portfolio` → **293 passés, 2 ignorés**.
Aucun module n'est câblé en production : ils entrent par le gate comme n'importe quel candidat
(`vault/15_CERTIFICATION.md`). **Statut : UNCALIBRATED** — aucun paramètre (Y de l'impact, κ de la
bande, seuils de demi-vie) n'a été mesuré sur tes données.

---

## 4. Séquence recommandée (dépendances, pas préférences)

**Vague 1 — rendre le passé immuable** (sans elle, aucune mesure ne vaut) :
F1 (prix bruts + table d'actions), F9 (`index_membership` datée), rendement de radiation.
→ Puis seulement : re-runner le gate sur les 8 hypothèses. Tant que l'historique mute, la
comparaison de deux verdicts DSR n'a pas de sens.

**Vague 2 — installer le thermomètre** : IC réalisé par facteur et par horizon, souffle
effectif, TC. Trois nombres qui disent, avant tout développement, si un IR de 1 est
atteignable ou arithmétiquement hors de portée (`ic_required`).

**Vague 3 — coût non linéaire partout** : brancher `impact.total_cost_bps` dans
`preset_backtest`, `screening/expectancy_filter`, et le sabotage. C'est le seul changement
qui peut *inverser* un verdict existant — donc à faire avant d'ajouter le moindre signal.

**Vague 4 — alpha non directionnel** : la cointégration est la réponse naturelle au constat
« DSR≈0 sur le directionnel » du [[12_MANIFESTE_HONNETETE]]. Précondition **architecturale** :
la vente à découvert (ADR-0029 = long-only v1). Sans short, pas de paire actions ; en crypto
spot non plus. C'est une décision à prendre explicitement, pas un détail d'implémentation.

**Vague 5 — exécution** : `exec_lag=1` par défaut, fill à la barre suivante plafonné par la
participation, dead-man switch, machine à états de dégradation. Prérequis de tout live et de
tout intraday.

---

## 5. Les cinq pièges institutionnels qui coûtent le plus cher ici

1. **Comparer deux backtests lancés à deux dates** sur une base de prix qui se réécrit (F1).
2. **Compter BR = N × T.** Avec 100 noms corrélés à 0,5 et un signal d'autocorrélation 0,9,
   le souffle effectif tombe à ~26 contre 25 200 en comptage naïf (facteur 960) : l'IR annoncé
   est surestimé d'un facteur ~31 (`effective_breadth` le chiffre en une ligne).
3. **Mesurer l'IC sur des rendements bruts** : on mesure alors surtout du bêta de marché.
4. **Optimiser un Sharpe** dont l'écart-type est calculé sous i.i.d. gaussien alors que
   l'indice de queue vaut ~3 (F5, F7) : l'incertitude réelle est bien plus large.
5. **Simuler des fills que le carnet n'aurait jamais donnés** — le biais qui fait passer une
   stratégie 1 h de « rentable » à « ruineuse » sans qu'aucune ligne de code ne change.
