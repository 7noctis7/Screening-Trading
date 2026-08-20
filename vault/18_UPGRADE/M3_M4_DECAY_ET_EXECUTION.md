# M3 & M4 — Décroissance de l'alpha, signaux chevauchants, exécution optimale

Retour à [[18_MODULES_AVANCES]].
Code : `packages/research/breadth.py`, `packages/execution/almgren_chriss.py`,
`packages/execution/impact.py`, `packages/research/alpha_decay.py`.

---

## M3.1 — Modèle de dépréciation et dimensionnement

Le signal suit un Ornstein-Uhlenbeck :

```
z_i(t + tau) = exp(−tau / theta) · z_i(t) + bruit        theta = demi_vie / ln 2
```

Estimation de `theta` sans supposer le modèle : `alpha_decay.ic_half_life` ajuste
`|IC(h)| ≈ IC_0 · exp(−h/theta)` sur les IC mesurés aux horizons h = 1, 2, …, H. Deux
garde-fous : ajuster en **log** (régression de `ln|IC(h)|` sur h, pente = −1/theta), et
refuser le résultat si le R² de cet ajustement est inférieur à ~0,6 — une décroissance non
exponentielle (plateau puis effondrement, ou rebond) invalide tout le raisonnement qui suit.

**Dimensionnement décroissant.** Une position ouverte sur un signal d'âge `a` ne mérite plus
la taille initiale :

```
poids(a) = poids_0 · exp(−a / theta)
```

Trois conséquences opérationnelles, et une seule est intuitive :

1. **Sortie par extinction, pas par seuil.** Couper quand `exp(−a/theta) < 0,25`, soit
   `a > 2·theta ≈ 2,9 × demi-vie`. Un stop temporel arbitraire (« 10 jours ») est un
   hyperparamètre de plus ; celui-ci est mesuré.
2. **Ne pas re-payer le spread pour suivre la décroissance.** Réduire continûment une
   position pour épouser `exp(−a/theta)` coûte du turnover pour un gain d'espérance nul.
   La bande de non-trading (`impact.no_trade_band`) doit dominer : on ne réduit que lorsque
   l'écart au poids cible dépasse la bande.
3. **Le rafraîchissement du signal réinitialise l'âge, pas le poids.** Si un nouveau signal
   confirme, l'âge repart de zéro ; mais le poids cible reste borné par le sizing global,
   sinon un signal persistant devient une position à levier croissant.

**Horizon optimal.** L'IC à l'horizon h suit `(1 − exp(−h/theta)) / sqrt(h)`, dont la
dérivée s'annule en `u* ≈ 1,2564` (u = h/theta) :

```
h* ≈ 1,81 × demi-vie de l'IC              (breadth.optimal_horizon, vérifié numériquement)
```

Détenir moins longtemps = payer des coûts pour une fraction de l'alpha ; détenir plus
longtemps = diluer un signal éteint dans du bruit. C'est ce nombre — pas une préférence —
qui dit sur quel timeframe un signal a le droit d'exister.

## M3.2 — Signaux chevauchants : ne pas fausser IR = IC·√BR

Trois corrections, toutes livrées ou spécifiées :

**a) Souffle effectif** (`breadth.effective_breadth`)
```
N_eff = N / (1 + (N − 1)·rho_coupe)
T_eff = T · (1 − rho_temps) / (1 + rho_temps)
BR_eff = N_eff · T_eff
```
`rho_temps` n'est pas un paramètre : c'est l'autocorrélation du signal entre deux décisions,
donc `exp(−p/theta)` avec `p` la période de rebalancement. Les deux modèles se rejoignent —
un signal lent A une autocorrélation élevée, ce qui EST la raison de son faible souffle.

**b) Rendements chevauchants** — un robot Daily détenant h barres produit une moyenne mobile
d'ordre `m = h/p`, d'autocorrélation `rho_k = (m − k)/m`. Le facteur d'annualisation devient
```
sqrt( périodes / (1 + 2·somme_{k=1..m−1} (1 − k/m)·rho_k) )
```
Sans correction, le Sharpe est gonflé d'environ `sqrt(m)`. Et le DSR doit utiliser
`n_eff = n / (1 + 2·somme_k (1−k/m)·rho_k)` — le `sr_std = sqrt(1/n)` réparé en juillet
suppose l'indépendance, qui est exactement ce que le chevauchement détruit.

**c) Robots multiples** — ne jamais additionner les souffles. Protocole : corréler les
vecteurs de poids cibles, puis les PnL quotidiens ; au-delà de 0,7 sur les PnL, c'est **une**
stratégie, garder celle dont l'IR net est le meilleur. Sinon, comparer l'IR du livre combiné
à `sqrt(IR_1² + IR_2²)` : l'écart chiffre la redondance résiduelle.

**d) Coefficient de transfert** — `TC = corrélation(alphas souhaités, poids réels)`. Le
produit des contraintes (long-only, plafonds, bandes, gross piloté par la vol, gates) peut
ramener le TC à 0,3, soit 70 % de l'IR perdu avant toute discussion sur l'alpha. Deux lignes
à ajouter dans le backtest.

---

## M4 — Exécution optimale d'Almgren-Chriss

### Le compromis
Exécuter vite = payer l'impact (coût **certain**). Exécuter lentement = subir la volatilité
du prix pendant l'exécution (coût **aléatoire**). Le second est le risque d'exécution, et
c'est celui que les backtests ignorent entièrement.

### Le modèle
Liquidation de X titres en N intervalles de durée `tau = T/N` ; `x_j` = titres restants en
`t_j = j·tau` ; `n_j = x_(j−1) − x_j` les trades.

```
impact permanent   g(v) = gamma · v          (déplace durablement le prix)
impact temporaire  h(v) = epsilon·signe(v) + eta · v     (payé sur CE trade seulement)

eta_tilde = eta − gamma·tau/2

E[coût]   = gamma·X²/2 + epsilon·somme|n_j| + (eta_tilde/tau)·somme n_j²
Var[coût] = sigma² · tau · somme x_j²
```

Le terme `gamma·X²/2` ne dépend **pas** de la trajectoire : l'impact permanent est le prix
d'entrée, pas un levier d'optimisation. Seule la répartition dans le temps se choisit.

### La solution
Minimiser `E + lambda·V` donne une récurrence linéaire du second ordre dont la solution est

```
cosh(kappa·tau) = 1 + (lambda·sigma²/eta_tilde) · tau²/2

x_j = X · sinh( kappa·(T − t_j) ) / sinh( kappa·T )
n_j = 2·sinh(kappa·tau/2)/sinh(kappa·T) · cosh( kappa·(T − t_(j−1/2)) ) · X
```

Propriétés, toutes testées :
- `lambda → 0` ⇒ `kappa → 0` ⇒ trajectoire **linéaire = TWAP** exact ;
- `lambda` croissant ⇒ `kappa` croissant ⇒ exécution **concentrée au début** ;
- `1/kappa` est le **temps caractéristique** de liquidation : il **ne dépend pas de X**. La
  taille change le coût, jamais le rythme. C'est le résultat le moins intuitif et le plus
  utile : inutile de recalibrer la forme pour chaque ordre.
- `eta_tilde <= 0` ⇒ le module **refuse** de renvoyer une trajectoire (intervalles trop longs
  devant l'impact temporaire), au lieu de produire un `arccosh` d'un argument invalide.

### La frontière efficiente d'exécution
`efficient_frontier()` renvoie `(coût espéré, écart-type)` pour une grille de `lambda`. C'est
l'objet à regarder, pas un `lambda` unique : il donne le prix, en bps, de chaque unité de
risque d'exécution évitée. **`lambda` est une décision de politique de risque, jamais un
paramètre à optimiser sur l'historique** — l'optimiser, c'est ajouter un essai au DSR pour
un gain qui n'existe que dans l'échantillon.

### Fragmenter un bloc issu du screener
1. Agréger les ordres par symbole et par sens (jamais d'aller-retour interne payé deux fois).
2. Rejeter d'abord ce qui ne passe pas l'admission `alpha > k · coût_aller_retour`
   (`impact.admit_signal`) — inutile d'optimiser l'exécution d'un trade qui ne doit pas exister.
3. Calibrer `eta` et `gamma` sur le TCA réel (cf. [[17_AUDIT_INSTITUTIONNEL]] axe 4) ; à
   défaut, partir de `eta ≈ sigma / (0,1·ADV)` et `gamma ≈ eta/10`, et **le dire**.
4. Calculer la trajectoire, puis **écrêter au plafond de participation**
   (`cap_by_participation`). Si le plafond mord, l'horizon est **infaisable** : l'allonger,
   jamais écrêter en silence — écrêter transforme une trajectoire optimale en trajectoire
   arbitraire dont le résidu n'est jamais exécuté.
5. Sur plusieurs symboles, la variance est un objet **de portefeuille** :
   `Var = somme_t tau · x_t' · Sigma · x_t`. Optimiser chaque symbole isolément sur-estime le
   risque total quand les jambes se compensent (une paire long/short se liquide plus
   lentement, pas plus vite). C'est la version multi-actifs d'Almgren-Chriss, et elle exige
   la covariance **débruitée** de [[M1_RMT_COVARIANCE]].

### Pièges d'implémentation
- **Unités.** `sigma` est en MONNAIE par titre et par racine d'unité de temps, `eta` en
  monnaie par titre et par (titre/unité de temps). Mélanger une vol en pourcentage et un eta
  en dollars donne un `kappa` faux de plusieurs ordres de grandeur — et une trajectoire
  plausible en apparence. Tester `kappa` contre `cosh(kappa·tau)` à chaque changement.
- **Profil de volume.** Le modèle suppose une liquidité homogène. En pratique, le volume est
  en U : une trajectoire front-loadée exécute à l'heure la plus liquide, ce qui la favorise
  au-delà de ce que le modèle dit. Corriger en exprimant `tau` en **temps de volume** (volume
  clock) plutôt qu'en temps calendaire.
- **Signal vivant pendant l'exécution.** Almgren-Chriss suppose une valeur de liquidation
  fixe. Si l'alpha se déprécie pendant l'exécution (M3.1), l'urgence augmente : le terme de
  décroissance `exp(−t/theta)` s'ajoute au coût d'opportunité et pousse `kappa` vers le haut.
  Approximation opérationnelle acceptable : majorer `lambda` d'un facteur `1 + T/theta`.
