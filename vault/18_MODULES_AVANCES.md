# 18 — MODULES AVANCÉS (RMT · CPCV · Almgren-Chriss · Portage · Quantamental · Alt-Data)

> Suite directe de [[17_AUDIT_INSTITUTIONNEL]]. L'audit disait **quoi réparer** ; ces notes
> donnent les **spécifications exécutables** des sept modules demandés, et six d'entre eux
> sont livrés en code testé. Rien n'est câblé en production : tout entre par
> `packages/research/gate.py` (cf. `vault/15_CERTIFICATION.md`).

Détail : [[M1_RMT_COVARIANCE]] · [[M2_LABELLISATION_CV]] · [[M3_M4_DECAY_ET_EXECUTION]] ·
[[M5_QUEUES_ET_FINANCEMENT]] · [[M6_QUANTAMENTAL_NLP]] · [[M7_ALTDATA_OVERLAYS]]

---

## At a Glance — les cinq choses qui changent une décision

1. **La covariance du screener n'est pas exploitable telle quelle.** Avec n actifs et T
   observations, `q = n/T` gouverne tout. Le seuil de Marčenko-Pastur dit combien de
   directions sont réellement estimables ; sur les fenêtres courtes du preset, la réponse
   est souvent **une ou deux**. Une optimisation transversale sur une matrice de rang
   effectif 2 n'optimise rien — elle range du bruit. `denoise_covariance()` rend ce verdict
   en une ligne, avant toute allocation.
2. **La CV purgée actuelle ne produit qu'un seul chemin de backtest.** Elle donne une
   performance hors échantillon, pas sa **dispersion** — or c'est la dispersion qui décide.
   La CPCV (n=6, k=2) donne 15 découpages et **5 chemins**, donc une distribution de Sharpe :
   c'est la seule entrée honnête du PBO et du Sharpe déflaté.
3. **La taille d'échantillon effective est un ordre de grandeur plus petite que le nombre de
   lignes.** Avec des labels à 10 barres décalés de 1, 200 échantillons valent **moins de 30**
   paris indépendants. Tout test de significativité qui utilise 200 se trompe d'un facteur 2,6
   sur les écarts-types.
4. **La forme optimale d'exécution ne dépend pas de la taille de l'ordre.** Le temps
   caractéristique `1/kappa` d'Almgren-Chriss est indépendant de X : la taille change le coût,
   jamais le rythme. Ce qui change le rythme, c'est l'aversion au risque d'exécution — un
   paramètre de politique, à ne pas optimiser sur l'historique.
5. **Sur un titre difficile à emprunter, le prêteur capte l'edge avant toi.** `max_borrow_fee()`
   donne le nombre à exiger du courtier AVANT d'ouvrir un short : au-delà, la paire est
   rentable pour tout le monde sauf pour le compte.

---

## Code livré cette session (901 tests verts, +50)

| Module | Fichier | Ce qu'il calcule | Tests |
|---|---|---|---|
| **M1** | `packages/portfolio/rmt_denoise.py` | Bornes de Marčenko-Pastur, nombre de facteurs par point fixe **et** écart spectral, débruitage à valeur propre résiduelle constante, détonage, rang effectif, chaîne complète MP → Ledoit-Wolf | 8 |
| **M2** | `packages/ml/cpcv.py` | CV combinatoire purgée avec embargo, nombre de chemins `C(n,k)·k/n`, reconstitution des chemins | 6 |
| **M2** | `packages/ml/uniqueness.py` | Concurrence, unicité moyenne, poids par attribution de rendement, décroissance temporelle, **taille d'échantillon effective** | 6 |
| **M3** | `packages/research/breadth.py` *(session 17)* | Souffle effectif, coefficient de transfert, IR = IC·√BR·TC, horizon optimal ≈ 1,81 × demi-vie | 8 |
| **M3/M6** | `packages/ranking/orthogonalize.py` | z robuste médiane/MAD, z intra-groupe avec taille minimale, QR séquentiel, **projection de neutralisation**, exposition factorielle, combinaison `Omega⁻¹·ic` | 6 |
| **M4** | `packages/execution/almgren_chriss.py` | `kappa` par résolution de cosh, trajectoire `sinh`, coût espéré et variance, frontière efficiente d'exécution, plafond de participation | 8 |
| **M4** | `packages/execution/impact.py` *(session 17)* | Impact racine carrée, taille max sous budget, test d'admission | 7 |
| **M5** | `packages/portfolio/sizing/kelly_fat_tail.py` *(session 17)* | Kelly empirique + queue GPD, fraction dérivée d'un budget de drawdown | 7 |
| **M5** | `packages/execution/funding_costs.py` | Financement de marge, rebate de prêt de titres, dividendes short, coût du capital bloqué, **frais d'emprunt maximal supportable** | 8 |
| **M7** | `packages/research/causality.py` | Bêta incomplète et p-value de Fisher (sans scipy), **Granger bidirectionnel**, information mutuelle Miller-Madow, test par permutation, alignement point-in-time, correction Šidák | 8 |

Seul **M6** (quantamental / NLP) n'apporte pas de nouveau module : `packages/sentiment/`
existe déjà (FinBERT + lexique + RSS point-in-time + `history.record_and_delta`). Ce qui lui
manque n'est pas du code de scoring mais un **protocole** — cf. [[M6_QUANTAMENTAL_NLP]].

---

## Blueprint d'assemblage (l'ordre de branchement, pas un exemple jouet)

```python
# 1. RISQUE — la covariance décide si l'optimisation a un sens
from packages.portfolio.rmt_denoise import denoise_covariance
risk = denoise_covariance(returns_matrix)          # n × T, lignes = actifs
if not risk["available"] or risk["k_signal"] < 2:
    raise RuntimeError(f"covariance non exploitable : {risk.get('verdict')}")

# 2. SIGNAL — z robuste, neutralisation factorielle, combinaison par Omega^-1 ic
from packages.ranking.orthogonalize import group_z, neutralize, combine_signals
Z = np.column_stack([group_z(raw[f], secteurs) for f in facteurs])
comb = combine_signals(Z, ics_mesures)             # ics = IC RÉALISÉS, jamais supposés
alpha = neutralize(comb["score"], loadings_B, weights=1 / var_specifique)

# 3. LOI FONDAMENTALE — l'IR est-il atteignable ? (avant de coder quoi que ce soit)
from packages.research.breadth import ir_report, optimal_horizon
diag = ir_report(ic=comb["ic_combined"], n_names=len(alpha), n_periods=252,
                 rho_cross=rho_signaux, rho_time=rho_temps, tc=tc_mesure)
horizon = optimal_horizon(demi_vie_ic)             # ≈ 1,81 × demi-vie

# 4. TAILLE — Kelly à queues épaisses, puis contraintes dures
from packages.portfolio.sizing.kelly_fat_tail import sized_fraction
from packages.execution.impact import max_qty_for_budget, participation_cap, admit_signal
f = sized_fraction(roundtrips_reels, dd_limit=0.25, dd_prob=0.05)
q = min(qty_cible, max_qty_for_budget(...), participation_cap(adv, minutes))
if not admit_signal(alpha_bps, cout_bps, k=2.0)["admitted"]:
    q = 0                                          # l'alpha ne paie pas le passage

# 5. EXÉCUTION — trajectoire optimale, puis plafond de carnet
from packages.execution.almgren_chriss import trajectory, cap_by_participation
traj = trajectory(q, horizon=1.0, n_steps=20, sigma=sigma_prix, eta=eta, gamma=gamma,
                  lam=aversion_execution, epsilon=demi_spread)
plan = cap_by_participation(traj["trades"], volume_barre, pov=0.10)
if not plan["feasible"]:
    ...                                            # allonger l'horizon, jamais écrêter

# 6. NET — ce qui reste après portage
from packages.execution.funding_costs import carry_costs, net_expected_return
carry = carry_costs(nav, long_notional, short_notional, borrow_fee=frais_reels)
net = net_expected_return(alpha_brut_bps, cout_transaction_bps, carry["total_carry_bps"])

# 7. VALIDATION — CPCV + unicité, jamais un K-fold naïf
from packages.ml.cpcv import CombinatorialPurgedCV
from packages.ml.uniqueness import average_uniqueness, effective_sample_size
u = average_uniqueness(t0, t1)                     # poids ET n effectif
for train, test, _ in CombinatorialPurgedCV(6, 2, embargo_pct=0.01).split(t0, t1):
    ...                                            # 15 découpages → 5 chemins → PBO/DSR
```

---

## Correspondance avec le framework de screening en 5 modules

| Framework demandé | Traité dans | État |
|---|---|---|
| 1 · Extraction de signaux — value/quantamental | [[M6_QUANTAMENTAL_NLP]] | `packages/fundamentals` (DCF, ratios) + `sentiment` existent ; protocole NLP spécifié |
| 1 · Momentum vs retour à la moyenne | [[M3_M4_DECAY_ET_EXECUTION]] | La **demi-vie de l'IC** tranche : signe et vitesse de décroissance ; `optimal_horizon` livré |
| 1 · Cointégration, OFI, carnet | `packages/research/cointegration.py` + `microstructure.py` | Livrés (Engle-Granger, ADF, demi-vie ; OFI/vPIN) ; Johansen : spec dans [[M1_RMT_COVARIANCE]] § 5 |
| 1 · Microstructure crypto (funding, OI, skew, liquidations) | [[M7_ALTDATA_OVERLAYS]] | `data/funding.py` + `deriv_normalizer.py` existent ; OI et skew à ajouter |
| 2 · Biais comportementaux, régimes conditionnels | [[17_AUDIT_INSTITUTIONNEL]] axe 3 + [[M7_ALTDATA_OVERLAYS]] | HMM causal spécifié ; overlays de régime livrés dans le preset |
| 3 · Modèle multi-facteurs, VCV shrinkée, surface de vol | [[M1_RMT_COVARIANCE]] + [[M5_QUEUES_ET_FINANCEMENT]] | RMT + Ledoit-Wolf livrés ; **surface de volatilité et grecques : NON couverts, aucune donnée d'options dans le dépôt** |
| 4 · MVO / CVaR / Kelly | [[M5_QUEUES_ET_FINANCEMENT]] | Kelly livré ; **CVaR-optimisation (Rockafellar-Uryasev) spécifiée, non implémentée** (exige `scipy.optimize.linprog`, groupe `quant` déjà déclaré) |
| 5 · Backtest sans biais, métriques | [[17_AUDIT_INSTITUTIONNEL]] axes 1 et 5 | Security master et corporate actions spécifiés ; CPCV et unicité livrés |

**Deux trous assumés et non comblés** : la couverture optionnelle dynamique (aucune chaîne
d'options n'est ingérée — le sujet n'est pas « à implémenter », il est « à décider », car il
change la classe d'actifs du projet), et l'optimisation CVaR par programmation linéaire
(spécifiée en [[M5_QUEUES_ET_FINANCEMENT]] § 3, non codée faute de pouvoir la tester ici).
