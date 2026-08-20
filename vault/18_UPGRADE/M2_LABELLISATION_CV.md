# M2 — Labellisation microstructurelle et validation croisée (1 h / 4 h)

Retour à [[18_MODULES_AVANCES]]. Code : `packages/ml/cpcv.py`, `packages/ml/uniqueness.py`.
Existant audité : `packages/ml/labeling.py`, `packages/ml/cv.py`.

## 1. Triple-barrière : la spécification, et ce qui manque à l'implémentation actuelle

Pour une entrée en `t_i`, trois barrières :

```
haute   :  prix · ( 1 + pt · sigma_ewma(t_i) · sqrt(h) )
basse   :  prix · ( 1 − sl · sigma_ewma(t_i) · sqrt(h) )
verticale : t_i + h                       (h = horizon, en BARRES)

label = +1 si la haute est touchée en premier
        −1 si la basse est touchée en premier
         signe du rendement si seule la verticale est atteinte (ou 0 si l'on veut
         un problème à trois classes — décision à documenter, pas à subir)
```

`sigma_ewma` est la volatilité EWMA des rendements, calculée **causalement** :
```
mu_t  = alpha·r_t + (1−alpha)·mu_(t−1)
var_t = alpha·(r_t − mu_t)² + (1−alpha)·var_(t−1)         alpha = 2/(span+1)
```
L'implémentation existante est causale — c'est acquis, et c'est l'essentiel.

**Quatre écarts à corriger** dans `labeling.triple_barrier` :

1. **Pas de mise à l'échelle par l'horizon.** Les barrières valent `pt·vol[i]` où `vol` est
   la volatilité d'**une** barre. Sur un horizon de 20 barres, une barrière à 2 volatilités
   d'une barre est touchée presque à coup sûr : le label devient du bruit de haute
   fréquence. Il faut `pt · sigma · sqrt(h)`, sans quoi le rapport profit/stop n'a aucun
   sens économique.
2. **Détection sur le close uniquement.** Un stop touché en séance mais non clôturé au-delà
   n'est pas vu : biais **optimiste** systématique, exactement du côté qui flatte. Utiliser
   `high`/`low`. Et quand les deux barrières sont touchées dans la même barre, l'ordre est
   indéterminé : le seul choix honnête est **la plus défavorable** (le stop), sauf à
   disposer de données infra-barre.
3. **Pas de barrières asymétriques ni de côté.** Un label de short doit inverser les
   barrières. En l'état, `meta_labels(side=-1)` corrige le signe du PnL mais pas la
   géométrie des barrières.
4. **`t1` doit être exporté systématiquement** pour la purge. `Label.exit_idx` le fournit —
   il faut que TOUS les appelants le propagent jusqu'à la CV, sinon la purge ne protège rien.

Piège propre à l'intraday : la barrière verticale doit être exprimée en **temps de marché**,
pas en nombre de lignes. Vingt barres horaires à cheval sur un week-end crypto ≠ vingt barres
d'une séance actions. Sur actions, une barrière verticale qui traverse la clôture doit
compter le gap d'ouverture comme un événement, pas comme une continuité.

## 2. Purge et embargo : ce que fait déjà `PurgedKFold`

La purge est correctement implémentée : tout échantillon d'entraînement dont l'intervalle
`[t0, t1]` chevauche la fenêtre de test est retiré, embargo compris. Deux remarques :

- l'embargo est exprimé en fraction de l'**empan temporel total**, ce qui est la convention
  d'AFML — mais sur des robots 1 h, 1 % de deux ans fait ~5 jours d'embargo, ce qui est
  généreux ; le calibrer sur la **demi-vie de l'autocorrélation des résidus**, pas sur une
  fraction arbitraire ;
- `np.array_split` découpe par **position d'échantillon** : cela n'a de sens que si les
  échantillons sont triés par `t0`. `cv.py` ne le vérifie pas ; `cpcv.py` **lève une
  exception** si ce n'est pas le cas. C'est la différence entre une garde et une convention.

## 3. Validation croisée combinatoire purgée (CPCV)

Le défaut structurel du K-fold purgé : il produit **un seul chemin** de backtest. On obtient
un Sharpe hors échantillon, jamais sa dispersion — donc rien à donner au PBO ni au DSR.

La CPCV teste `k` groupes parmi `n` à chaque itération :

```
nombre de découpages :  C(n, k)
chemins reconstitués :  phi = C(n, k) · k / n

n = 6, k = 2  →  15 découpages, 5 chemins
n = 10, k = 2 →  45 découpages, 9 chemins
```

Chaque groupe est testé dans `C(n−1, k−1)` découpages ; en recomposant une prédiction par
groupe et par chemin, on obtient **phi courbes de performance hors échantillon complètes**.
La sortie utile n'est pas leur moyenne mais leur **distribution** : médiane, dispersion, et
proportion de chemins à Sharpe négatif — c'est la définition opérationnelle du PBO.

Coût à mesurer avant de choisir `n` : `C(n,k)` entraînements. Sur un robot 1 h avec un
modèle à gradient boosting, n=10, k=2 signifie 45 entraînements par essai d'hyperparamètre.
La CPCV est un budget, pas une option gratuite.

## 4. Unicité : pourquoi 200 lignes valent 26 observations

Des labels à barrière se chevauchent. Trois quantités, toutes livrées :

```
concurrence         c(t)  = nombre de labels actifs à la barre t
unicité moyenne     u_i   = moyenne de 1/c(t) sur [t0_i, t1_i]
taille effective    n_eff = somme des u_i
```

Mesuré : 200 labels de 10 barres décalés de 1 barre donnent `n_eff < 30`. Trois usages :

1. **Tests de significativité** : utiliser `n_eff`, jamais le nombre de lignes. C'est le
   pendant, côté apprentissage, du souffle effectif de [[17_AUDIT_INSTITUTIONNEL]] axe 2 —
   et du `n_eff` du DSR.
2. **Poids d'échantillon** par attribution de rendement : `w_i ∝ |somme de r(t)/c(t)|`. Un
   label qui traverse une période calme et partagée pèse moins qu'un label qui capte seul un
   mouvement franc. Sans cette pondération, le modèle optimise majoritairement du bruit.
3. **Bagging honnête** : tirer `max_samples = moyenne des u_i` (et non 1,0) évite qu'un
   arbre voie dix copies de la même information et croie à dix confirmations.

`time_decay_weights(u, last_weight)` ajoute la décroissance linéaire en temps d'unicité
cumulé : `last_weight = 1` désactive, `0` annule la plus ancienne observation, **négatif**
écarte purement les plus anciennes — à réserver aux changements de régime documentés, jamais
comme réglage libre (c'est un hyperparamètre déguisé, donc un essai à compter dans le DSR).

## 5. Enchaînement correct pour un robot 1 h ou 4 h

1. Barres construites sur un calendrier d'échange réel, étiquetées à la clôture, en UTC.
2. `sigma_ewma` causale → barrières `pt·sigma·sqrt(h)`, détection sur high/low, ex-æquo
   résolu en faveur du stop.
3. Export de `(t0, t1)` pour **chaque** échantillon.
4. `average_uniqueness` → poids d'échantillon et `n_eff`.
5. `CombinatorialPurgedCV(n=6, k=2, embargo_pct=…)` → 5 chemins.
6. Distribution des Sharpe des 5 chemins → PBO, puis DSR avec `n_eff` et non `n`.
7. Meta-labeling seulement ensuite : le modèle primaire donne le SENS, le méta-modèle
   décide d'AGIR. Séparer les deux permet de dimensionner sur une probabilité calibrée
   (`packages/ml/calibration.py` existe) plutôt que sur un score brut.

Piège final, spécifique à l'intraday : la fuite ne vient presque jamais du modèle, elle vient
des **features**. Une moyenne mobile centrée, un `bfill`, une normalisation calculée sur tout
l'échantillon, un feature store rebâti après coup — tous produisent des scores hors
échantillon splendides et un live plat. Le sous-agent `leakage-hunter` du dépôt existe pour
ça : le passer systématiquement avant chaque entraînement.
