# AXE 2 — Ingénierie du signal & loi fondamentale de la gestion active

Retour à [[17_AUDIT_INSTITUTIONNEL]]. Code livré : `packages/research/breadth.py`.

> `IR = IC · √BR` (Grinold-Kahn) est presque toujours cité, presque jamais mesuré. La version
> utilisable est celle de Clarke-de Silva-Thorley : **IR = IC · √BR · TC**, où TC (coefficient
> de transfert) est ce qui survit aux contraintes. Les trois termes se mesurent ; aucun n'est
> mesuré dans le dépôt aujourd'hui.

## 1. Du score au rendement espéré

Un z-score n'est pas un alpha. La conversion (Grinold) est :

```
alpha_i(h) = sigma_i(h) · IC(h) · z_i
```

- `sigma_i(h)` = volatilité **résiduelle prévue** de i sur l'horizon h (pas la vol totale,
  pas la vol annualisée si h est quotidien) ; `sigma_i(h) = sigma_i,jour · √h`.
- `IC(h)` = corrélation de rang **réalisée, hors échantillon**, entre `z_i(t)` et le rendement
  **résiduel** de t à t+h. Sur rendement brut, on mesure surtout du bêta de marché.
- `z_i` = score standardisé en **coupe transversale**, écrêté à ±3.

Cette formule est ce qui rend un score consommable par un optimiseur : elle porte l'unité
« rendement », et son échelle (donc le levier implicite) est fixée par l'IC, pas par un
paramètre libre. Implémentation : `breadth.alpha_from_ic`.

### Corriger le z-score (finding F6)
`packages/ranking/engine.py:_zscore` utilise moyenne/écart-type sans winsorisation. Sur des
distributions à queues épaisses, un seul point déplace `mu` et écrase tout le classement.
Version robuste :
```
médiane m = median(x) ; MAD = median(|x − m|)
z_i = 0,6745 · (x_i − m) / MAD          (0,6745 = MAD → écart-type gaussien)
z_i ← clip(z_i, −3, +3)
```
Trois garde-fous supplémentaires :
1. **Taille de groupe minimale** pour le démoyennage sectoriel : n ≥ 10, sinon repli global.
   Un secteur à deux noms produit mécaniquement ±1 — du bruit promu en signal.
2. **Compter les NaN** : `NaN → 0` est acceptable (0 = neutre), mais si 40 % de l'univers est
   neutre, le classement porte sur 60 % de l'univers et il faut le dire.
3. **Standardiser après winsorisation**, jamais l'inverse.

### Combiner plusieurs signaux
Avec un vecteur d'IC `ic` (un par signal) et la matrice de corrélation `Omega` **des signaux
entre eux** :
```
w* ∝ Omega⁻¹ · ic          (pondération optimale)
IC_combiné = √( ic' · Omega⁻¹ · ic )
```
Une moyenne pondérée à la main est le cas particulier `Omega = I` — c'est-à-dire l'hypothèse
que momentum et trend ne se ressemblent pas, ce qui est faux. `Omega⁻¹` est instable : la
rétrécir (`Omega_sh = (1−delta)·Omega + delta·I`, Ledoit-Wolf) n'est pas une précaution, c'est
la condition de stabilité hors échantillon.

---

## 2. Décroissance temporelle : 1 h → 4 h → Daily → Weekly → Monthly

Modèle : le signal suit un OU, `z_i(t+tau) = exp(−tau/theta) · z_i(t) + bruit`, avec
`theta = demi-vie / ln 2`. `packages/research/alpha_decay.py` estime déjà la demi-vie de l'IC.

**Ce qui change avec l'horizon n'est pas le z-score, c'est ce qui le multiplie.**
Le rendement espéré cumulé sur h croît en `(1 − exp(−h/theta))` (le signal s'éteint) tandis
que l'écart-type du rendement croît en `√h`. Donc :

```
IC(h) ∝ (1 − exp(−h/theta)) / √h
```

L'annulation de la dérivée donne `2u·exp(−u) = 1 − exp(−u)`, soit `u* ≈ 1,2564` :

```
horizon de détention optimal  h* ≈ 1,81 × demi-vie de l'IC
```

(vérifié numériquement dans `tests/research/test_breadth.py`, fonction `optimal_horizon`).

Conséquence opérationnelle immédiate : **mesure la demi-vie, elle te dit sur quel timeframe le
signal a le droit d'exister.** Un signal de demi-vie 3 heures n'a rien à faire dans un robot
Weekly — il y sera dilué dans du bruit. Un signal de demi-vie 40 jours n'a rien à faire dans un
robot 1 h — il y paiera 100 fois le coût pour le même alpha.

### Et le souffle ?
Le nombre de décisions par an vaut `T(h) = périodes_par_an / h`. En combinant :
```
IR_brut(h) ∝ IC(h) · √T(h) ∝ (1 − exp(−h/theta)) / h
```
qui est **décroissante en h** : à coût nul, plus court est toujours mieux. C'est exactement
pourquoi l'intraday est séduisant — et pourquoi tout s'y joue sur les coûts, puisque le coût
annuel croît en `1/h` lui aussi. L'arbitrage se règle donc **entièrement** par le test
d'admission de l'[[AXE4_SIZING_FRICTIONS]] § 4.5, jamais par l'intuition.

---

## 3. Signaux chevauchants : ne pas surestimer BR

C'est le point le plus coûteux de la loi fondamentale, et le plus souvent bâclé.

### 3.1 Souffle effectif
```
N_eff = N / (1 + (N − 1) · rho_coupe)        rho_coupe = corrélation moyenne des signaux
T_eff = T · (1 − rho_temps) / (1 + rho_temps) rho_temps = autocorrélation du signal
BR_eff = N_eff · T_eff
```
Ordres de grandeur (calculés par `breadth.effective_breadth`) : 100 noms corrélés à 0,5 et un
signal d'autocorrélation 0,9 donnent `N_eff ≈ 2,0` et `T_eff ≈ 13` sur 252 jours, soit
`BR_eff ≈ 26` contre 25 200 en comptage naïf (facteur 960). **L'IR annoncé est surestimé d'un facteur ~31.**
Un IR « théorique » de 3 devient 0,1.

Utilisation la plus rentable — avant d'écrire du code :
```
IC_requis = IR_cible / (√BR_eff · TC)         → breadth.ic_required
```
Si l'IC requis dépasse 0,10 sur des données publiques quotidiennes, le projet est
arithmétiquement hors de portée : la littérature situe l'IC d'un facteur robuste entre 0,02 et
0,06. Ce calcul coûte une seconde et évite des mois.

### 3.2 Rendements chevauchants (Daily × Weekly)
Un robot Daily qui détient 5 jours produit une série de rendements en moyenne mobile d'ordre
`m = h/p` ; son autocorrélation théorique est `rho_k = (m − k)/m`. Deux conséquences :

1. **Annualisation.** `Sharpe_annuel = Sharpe_période · √(périodes) ` est faux ici. Le
   facteur correct est
   ```
   √( périodes / (1 + 2·somme_{k=1..m−1} (1 − k/m)·rho_k) )     (Newey-West / Lo 2002)
   ```
   Sans correction, le Sharpe est gonflé d'environ `√m`.
2. **DSR.** `packages/portfolio/psr.py` prend `sr_std = √(1/n)` (H0 de Bailey, i.i.d.). Sous
   chevauchement, `n` doit être remplacé par le nombre d'observations **effectives**
   `n_eff = n / (1 + 2·somme_k (1 − k/m)·rho_k)`. Le correctif de juillet a réparé le
   thermomètre ; ce point-ci en règle la graduation.

### 3.3 Deux robots ne font pas deux paris
Protocole, dans cet ordre :
1. Corrélation des **vecteurs de poids cibles** des deux robots, date par date.
2. Corrélation de leurs **PnL quotidiens**.
3. Si `rho(PnL) > 0,7` → c'est **une** stratégie. Garder celle dont l'IR **net** est le
   meilleur, supprimer l'autre (parcimonie — c'est déjà l'esprit de l'ADR-0024).
4. Sinon, mesurer l'IR du **livre combiné** et le comparer à `√(IR_1² + IR_2²)`. Un écart
   important signale de la redondance que les corrélations moyennes n'ont pas vue.

Ne jamais additionner les `BR` de deux robots. Le seul souffle qui compte est celui du livre
consolidé, mesuré sur le panel des poids actifs agrégés.

### 3.4 Le coefficient de transfert (le diagnostic le moins cher du dépôt)
```
TC = corrélation( alphas souhaités , poids réellement pris )     → breadth.transfer_coefficient
```
Le `preset_backtest` empile : long-only, plafond de poids adaptatif, bande de non-trading,
blackout ±move, `gross` piloté par la vol, gate de régime, gate d'ampleur. Chacun est
défendable ; **leur produit** peut ramener le TC à 0,3, c'est-à-dire jeter 70 % de l'IR avant
toute discussion sur l'alpha. Deux lignes à ajouter dans le backtest (`alphas` vs `w`)
répondent à la question « le problème vient-il du signal ou de mes contraintes ? ».

---

## 4. Orthogonalisation : isoler l'idiosyncratique (Paleologo)

Trois niveaux, du plus faible au plus juste.

### Niveau 1 — Démoyennage sectoriel (existant)
`sector_neutral=True` retire la moyenne du secteur. Nécessaire, très insuffisant : ne retire
ni le bêta de marché, ni la taille, ni la value, ni le momentum, ni le bêta **au** secteur
(seulement son niveau moyen).

### Niveau 2 — Régressions successives (Gram-Schmidt)
Ordonner les signaux par priorité économique, puis résidualiser chaque nouveau signal sur les
précédents déjà retenus :
```
s̃_k = s_k − somme_{j<k} beta_kj · s̃_j        beta_kj = <s_k, s̃_j> / <s̃_j, s̃_j>
```
Deux avertissements :
- **L'ordre est un choix**, pas une propriété : le premier signal conserve toute la variance
  partagée. Cet ordre doit faire l'objet d'un ADR, pas d'un `for` implicite.
- Ne pas coder Gram-Schmidt à la main : numériquement instable. Utiliser `Q, R = np.linalg.qr(S)` ;
  les colonnes de `Q` sont les signaux orthogonalisés dans l'ordre des colonnes de `S`.

### Niveau 3 — Neutralisation par le modèle de risque (la bonne)
Avec `B` (n × K) la matrice des expositions factorielles (bêta marché, taille, value,
momentum, vol, indicatrices sectorielles, facteurs statistiques) et `W` une matrice de poids
diagonale (l'inverse de la variance spécifique, ou √capitalisation) :

```
alpha_resid = alpha − B · (B' W B)⁻¹ · B' W · alpha
```

C'est la **projection** de l'alpha orthogonalement à l'espace des facteurs, dans la métrique W.
Sous-entendu crucial et souvent manqué : **neutraliser l'alpha ne neutralise pas le
portefeuille**. Si l'optimiseur qui suit utilise une covariance contenant ces mêmes facteurs,
il réintroduira les expositions. La contrainte doit être posée **dans l'optimiseur** :
`|B' w| <= epsilon`.

### D'où sortir `B` sans licence Barra
`packages/portfolio/factor_risk.py` fait déjà une ACP des rendements. Il manque le choix
rigoureux du nombre de facteurs — à faire par **Marchenko-Pastur** : pour n actifs et T
observations, les valeurs propres d'une matrice de bruit pur sont bornées par
```
lambda_max = sigma² · (1 + √(n/T))²
```
Ne garder que les valeurs propres **au-dessus** de cette borne : ce sont les seuls facteurs
distinguables du bruit. Prendre « les 3 premières » ou « 70 % de la variance » est arbitraire ;
ceci ne l'est pas. Et comme toujours : ACP estimée sur une fenêtre **passée**, jamais
plein-échantillon.

### Le test d'honnêteté final
Régresser les rendements quotidiens de la stratégie sur des facteurs publics et gratuits
(Ken French : Mkt-RF, SMB, HML, RMW, CMA, WML ; AQR : BAB, QMJ) :
```
r_strat(t) = alpha + somme_k beta_k · f_k(t) + eps(t)
```
- `alpha` non significatif (|t| < 2) ⇒ **le produit est un emballage de bêta**. Ce n'est pas
  disqualifiant — c'est la conclusion déjà assumée dans [[12_MANIFESTE_HONNETETE]] — mais cela
  doit être **écrit sur le tableau de bord**, à côté des KPI, pas dans une note.
- Publier aussi le `beta` au marché : un Calmar de 5 obtenu avec un bêta de 0,9 n'est pas un
  edge, c'est un choix d'exposition.
- Le `t` de l'alpha doit utiliser des écarts-types **Newey-West** (§ 3.2), sans quoi il est
  gonflé par le chevauchement.
