# AXE 3 — Risque de queue, régimes et arbitrage statistique

Retour à [[17_AUDIT_INSTITUTIONNEL]]. Code livré : `packages/research/cointegration.py`.

> Mandelbrot : les marchés sont invariants d'échelle, à mémoire longue, à lois de puissance.
> Taleb : optimiser un Sharpe, c'est optimiser un moment d'ordre 2 sur une distribution dont
> le moment d'ordre 4 n'existe peut-être pas. La conséquence pratique n'est pas d'abandonner
> le Sharpe, c'est de **mesurer d'abord à quel point il ment**.

## 1. Remplacer la variance par l'indice de queue

### 1.1 Estimer alpha (Hill) — le nombre manquant du tableau de bord
Sur les `k` pertes les plus grandes, triées décroissantes `X_(1) ≥ … ≥ X_(k+1)` :
```
xi_hat = (1/k) · somme_{i=1..k} [ ln X_(i) − ln X_(k+1) ]
alpha  = 1 / xi_hat
```
Choix de `k` : ne pas le fixer, **le balayer**. Tracer le « Hill plot » pour
`k ∈ [0,02·n , 0,10·n]` ; si `alpha` varie de plus de ±0,5 sur cette plage, la conclusion est
**UNCALIBRATED**, point. Sinon, retenir la médiane du plateau.

Lecture :
| alpha | Ce que cela implique |
|---|---|
| < 2 | variance infinie — le Sharpe **n'est pas défini** ; toute optimisation moyenne-variance est vide de sens |
| 2 – 4 | variance finie, **kurtosis infinie** — le Sharpe existe mais converge très lentement, et son écart-type usuel (qui contient la kurtosis) est invalide |
| > 4 | régime « presque gaussien » — les outils standards tiennent |

Ordres de grandeur publiés : actions ≈ 3–4, crypto ≈ 2,5–3,5. Autrement dit **le projet vit
très probablement dans la bande 2–4**, où l'intervalle de confiance du Sharpe est bien plus
large que ce que `psr.py` calcule. C'est un nombre à afficher à côté des KPI héros, au même
titre que le badge « MODÉLISÉ » ajouté en juillet.

### 1.2 Réparer l'estimateur GPD (finding F7)
`packages/portfolio/evt.py:fit_pot` estime `(xi, beta)` par la **méthode des moments**, qui
suppose une variance finie des excès, donc `xi < 0,5`. En crypto, `xi ≥ 0,5` est courant :
l'estimateur devient incohérent silencieusement.

Remplacer par les **moments pondérés par les probabilités** (PWM, Hosking-Wallis), formules
fermées, aucune dépendance. Avec les excès triés **croissants** `x_(1) ≤ … ≤ x_(n)` et
`p_i = (i − 0,35)/n` :
```
a0 = (1/n) · somme x_(i)
a1 = (1/n) · somme (1 − p_i) · x_(i)

xi   = 2 − a0 / (a0 − 2·a1)
beta = 2·a0·a1 / (a0 − 2·a1)
```
(Identités vérifiées analytiquement : pour une GPD(xi, beta), `a0 = beta/(1−xi)` et
`a1 = beta/(2·(2−xi))`, d'où `a0/(a0−2a1) = 2−xi` exactement ; le cas exponentiel `xi=0`
redonne `beta`.)

### 1.3 VaR et CVaR sous GPD
Avec `n` observations, `n_u` excès au-dessus du seuil `u` :
```
VaR_q = u + (beta/xi) · [ ( (n/n_u)·(1−q) )^(−xi) − 1 ]
ES_q  = ( VaR_q + beta − xi·u ) / (1 − xi)          valable pour xi < 1
```
**L'implémentation actuelle de `evt_var_es` est correcte** — seul l'estimateur en amont est à
changer. Rien d'autre à toucher.

### 1.4 Le piège du passage à l'échelle temporelle
`VaR_10j = √10 · VaR_1j` est faux hors gaussien. Sous stabilité stricte d'indice alpha, les
quantiles passent en `t^(1/alpha)` ; avec le clustering de volatilité, l'échelle empirique est
souvent **plus rapide** que ces deux règles. Conclusion pratique : **ne pas passer à
l'échelle du tout.** Deux voies honnêtes :
1. estimer la GPD directement sur les pertes à **h** jours (fenêtres chevauchantes, avec les
   écarts-types Newey-West de l'[[AXE2_ALPHA_LOI_FONDAMENTALE]] § 3.2) ;
2. bootstrap **par blocs** (le `Simulator.tsx` du front le fait déjà, blocs de 10 jours) —
   et aligner `psr.bootstrap_sharpe_ci`, aujourd'hui i.i.d., sur un bootstrap stationnaire
   (Politis-Romano, longueur de bloc géométrique de moyenne ≈ n^(1/3)). Finding F5.

### 1.5 Lois alpha-stables : recommandation explicite de ne pas les utiliser
Elles décrivent bien le **corps** de la distribution, mais imposent une variance infinie dès
`alpha < 2` et rendent l'estimation instable pour des queues qu'on veut justement chiffrer.
Le standard buy-side est **EVT (Hill + POT/GPD) pour la queue** et un modèle conditionnel
(GARCH — `packages/portfolio/garch.py` existe) pour le corps. Si un diagnostic stable est
souhaité, l'estimateur par quantiles de McCulloch suffit — comme **thermomètre**, jamais comme
base de dimensionnement.

---

## 2. Le vrai risque n'est pas la volatilité, c'est la dépendance de trajectoire

Le drawdown dépend de l'**ordre** des rendements ; ni la variance ni la CVaR à un jour ne le
capturent. Trois métriques à faire cohabiter, aucune ne remplaçant les autres :
- **CVaR_99 à 1 jour** (EVT) → dimensionne le risque instantané ;
- **CVaR de drawdown** (CDaR) : moyenne des `q%` pires drawdowns d'une simulation par blocs
  → dimensionne le risque de trajectoire, celui qui fait fermer un fonds ;
- **temps sous l'eau** (durée, pas amplitude) → la métrique que ton RDV paper du 06/08 doit
  regarder, parce que c'est celle qui décide si un humain tient le plan.

`packages/portfolio/` contient déjà `stress.py`, `scenarios.py`, `fragility.py`,
`correlation_shock.py`. Ce qui manque est un **budget** unique : « P(DD > 25 %) ≤ 5 % sur
12 mois », mesuré par bootstrap par blocs, et **opposable** — c'est-à-dire qui réduit
automatiquement le gross quand il est violé. Cf. [[AXE4_SIZING_FRICTIONS]] § 2.

---

## 3. Détection de régime : ce qu'il faut corriger (finding F3)

`packages/regime/vol_regime.py` a deux fuites potentielles, sans conséquence aujourd'hui
(l'appel vient d'`apps/api/snapshot.py`, donc du live) mais bloquantes dès qu'on le câble dans
une boucle de backtest :
1. `np.percentile(valid, [33, 66])` calcule les terciles sur **tout** l'historique, futur
   inclus. Un jour de 2016 est classé « calme » à l'aune de la volatilité de 2020.
2. `GaussianHMM(...).fit(x)` puis `predict(x)` : l'ajustement voit tout l'échantillon, et
   `predict` renvoie la séquence de Viterbi **lissée** — la probabilité `P(S_t | tout)` et non
   `P(S_t | information jusqu'à t)`.

### Spécification corrigée
1. **Fenêtre expansive** : à chaque date t, ajuster sur `[0, t]` seulement (ou fenêtre
   glissante de 3–5 ans), ré-ajuster mensuellement, jamais à chaque barre (coût + instabilité).
2. **Probabilité filtrée** : utiliser la récursion *forward* (`alpha_t`) normalisée,
   pas `predict`. `hmmlearn` expose `score_samples` → prendre la dernière ligne des
   postérieurs obtenus sur `[0, t]`, ce qui vaut la probabilité filtrée en t.
3. **Étiquetage stable** : après chaque ré-ajustement, **réordonner les états par volatilité
   moyenne croissante**. Sans cela, l'EM peut permuter les étiquettes d'un mois sur l'autre et
   le régime « stress » devient « calme » sans que rien ne le signale. C'est le bug le plus
   fréquent des HMM en production.
4. **Hystérésis** : entrer en stress au 80e centile, en sortir au 60e. Un seuil unique produit
   des allers-retours coûteux exactement quand les coûts explosent.
5. **Observation multivariée** plutôt que la seule vol réalisée :
   `x_t = [ r_t , ln RV_t , RV_5/RV_60 (structure par terme) , skew réalisée , spread de crédit
   ou VIX ]`. Trois états : tendance-calme / normal / stress.

### Ce que le régime a le droit de piloter
Le régime module l'**exposition** et les **règles d'engagement**, jamais le signal lui-même
(sinon on conditionne deux fois sur la même information) :
```
gross_final = gross_vol_target · m(régime) · taper(drawdown)
m = {calme: 1,0 · normal: 0,7 · stress: 0,4}    (valeurs actuelles, à re-gater)
```
Et surtout : **le multiplicateur de régime doit passer le gate au même titre qu'un signal
d'alpha.** Trois seuils × trois multiplicateurs = neuf paramètres choisis sur le même
historique que tout le reste ; c'est un candidat au surajustement comme un autre.

### Où le filtre de Kalman est vraiment utile
Pas pour les régimes (un HMM est le bon outil pour un état discret), mais pour un **paramètre
continu qui dérive** : le ratio de couverture d'une paire.
```
état      : beta_t = beta_{t−1} + w        w ~ N(0, Q)
mesure    : y_t = [x_t  1] · [beta_t  alpha_t]' + v      v ~ N(0, R)

prédiction : P⁻ = P + Q
innovation : e = y_t − H·theta ;  S = H·P⁻·H' + R
gain       : K = P⁻·H' / S
mise à jour: theta = theta + K·e ;  P = P⁻ − K·H·P⁻
```
Le signal de trading est l'**innovation normalisée `e/√S`** : c'est le z-score de Chan, et il
est **causal par construction** (aucune moyenne glissante calculée sur des données futures).
Réglage : `R` = variance résiduelle d'un MCO initial ; `Q = delta/(1−delta)·I` avec
`delta ≈ 1e−4` à `1e−5` (plus `delta` est grand, plus beta bouge vite).

---

## 4. Module Pairs Trading (spécification complète)

Rappel du constat interne : **DSR ≈ 0 sur le directionnel**. La cointégration est la réponse
structurelle, pas un signal de plus — elle change la nature du pari (relatif, pas directionnel).

### 4.0 Précondition architecturale, à trancher avant de coder
L'ADR-0029 fixe le **long-only v1**. Une paire actions exige la vente à découvert (Alpaca la
permet sur titres marginables ; coût d'emprunt et rappel possibles). Le spot crypto ne permet
pas de short → il faudrait des perpétuels (funding = coût de portage) ou renoncer. **C'est une
décision, pas une implémentation** : sans short, l'axe 4 du corpus reste inaccessible.

### 4.1 Génération des candidats
Jamais toutes les paires : 500 titres = 124 750 paires, et à 5 % on « découvre » ~6 200 paires
cointégrées par pur hasard. Restreindre **a priori** :
- même secteur/industrie (GICS), ou
- ETF contre son panier répliqué, ou
- doubles cotations / classes d'actions (GOOG-GOOGL), ou
- futures contre sous-jacent.
Puis appliquer la correction multi-tests : `cointegration.bonferroni_level(0.05, n_tests)`
(100 actifs → 4 950 paires → seuil individuel ≈ 1e−5, ce qui rend le test quasi impossible à
passer — **c'est le message** : il faut réduire l'espace de recherche, pas assouplir le seuil).

### 4.2 Tests (implémentés dans `packages/research/cointegration.py`)
1. `hedge_ratio(y, x)` — MCO sur la **fenêtre de formation** (12 mois), figée.
2. `adf_test(spread, kind="eg2")` — valeurs critiques **Engle-Granger** (−3,90 / −3,34 / −3,04
   à 1/5/10 %) et non ADF standard (−3,43 / −2,86 / −2,57). Réutiliser l'ADF standard sur un
   résidu **estimé** sur-rejette massivement : c'est l'erreur canonique du pairs trading retail.
3. `half_life(spread)` — OU : `Δs = a + b·s_{t−1}`, `demi-vie = −ln2/b`. `b ≥ 0` ⇒ pas de rappel.
4. `pair_verdict(...)` — exige la cointégration **dans les deux sens** (y~x et x~y). Une
   relation qui ne tient que dans un sens dépend d'un choix arbitraire de variable dépendante.
5. **Filtre complémentaire non implémenté, à ajouter** : compter les **traversées de la
   moyenne** sur la fenêtre de formation (≥ 12 attendues). Un spread qui passe l'ADF sans
   traverser sa moyenne est une tendance lente, pas un rappel.

### 4.3 Règles d'engagement
| Élément | Valeur de départ | Justification |
|---|---|---|
| Fenêtre de formation | 12 mois, **antérieure** à la fenêtre de trading | pas de fit plein-échantillon |
| Entrée | \|z\| ≥ 2 | z par Kalman (§ 3) ou fenêtre glissante |
| Sortie | z ≈ 0 (ou 0,5 pour économiser un aller-retour) | |
| Stop | \|z\| ≥ 4, **ou** demi-vie > 2× celle de formation, **ou** échec du re-test mensuel | un spread qui diverge n'est plus un spread |
| Horizon max | ≈ 3 × demi-vie | au-delà, capital immobilisé sans espérance |
| Neutralité | en dollars via le ratio de couverture | vérifier aussi la neutralité **au bêta** |

### 4.4 Coûts spécifiques aux paires (souvent oubliés, souvent fatals)
- **deux** spreads bid-ask par aller-retour, pas un ;
- **coût d'emprunt** de la jambe courte (un titre *hard-to-borrow* peut coûter 20 %/an — ce qui
  annule à lui seul l'edge d'une paire à demi-vie de 20 jours) ;
- **dividende de la jambe courte** = décaissement ;
- **rappel de titres** (*buy-in*) : risque opérationnel, à traiter comme un stop forcé ;
- en crypto perp : **funding** dans les deux sens, à intégrer au PnL du spread.

### 4.5 Pièges structurels
- **Événements d'entreprise** : une OPA fige le spread pour toujours. Interroger
  `packages/events/` avant chaque entrée ; sortir immédiatement à l'annonce.
- **Cointégration par le facteur commun** : en crypto, deux alt-coins « cointègrent » surtout
  via BTC. Résidualiser d'abord sur BTC (et sur ETH), sinon on prend deux fois le même pari
  directionnel en croyant être neutre.
- **Re-test permanent** : une paire cointégrée en 2023 ne l'est pas en 2026. Re-tester chaque
  mois, dénouer sans état d'âme quand le test échoue.
- **Gate obligatoire** : ce module entre en production par `packages/research/gate.py`
  (placebo → DSR → PBO → sabotage) comme tout le reste. Aucune exception pour « c'est de la
  stat-arb, c'est différent ».
