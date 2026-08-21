# M5 — Risque de queue et coûts de financement institutionnels

Retour à [[18_MODULES_AVANCES]].
Code : `packages/portfolio/evt.py`, `packages/portfolio/sizing/kelly_fat_tail.py`,
`packages/execution/funding_costs.py`.

## 1. Substituer des métriques d'asymétrie au ratio de Sharpe

Le Sharpe est un rapport de moments d'ordre 1 et 2. Sous loi de puissance d'indice `alpha`,
le moment d'ordre `k` n'existe que si `k < alpha`. Conséquence directe et rarement dite :

| Indice de queue | Ce qui existe | Ce que cela interdit |
|---|---|---|
| `alpha < 2` | moyenne seulement | Le Sharpe **n'est pas défini** ; MVO, risk-parity, vol-targeting sont vides de sens |
| `2 ≤ alpha < 4` | moyenne et variance | Le Sharpe existe mais son écart-type usuel contient la **kurtosis**, qui n'existe pas → tous les intervalles de confiance publiés sont faux |
| `alpha > 4` | jusqu'à l'ordre 4 | Les outils standards tiennent |

Estimation par Hill sur les `k` pertes les plus grandes, `k` **balayé** et non fixé :
```
xi = (1/k)·somme_{i=1..k} [ ln X_(i) − ln X_(k+1) ]          alpha = 1/xi
```
Si `alpha` varie de plus de ±0,5 sur `k ∈ [0,02n , 0,10n]`, la conclusion est UNCALIBRATED.
Ordres de grandeur publiés : actions ≈ 3–4, crypto ≈ 2,5–3,5 — donc le projet vit très
probablement dans la bande où le Sharpe existe mais ment sur sa propre précision.

**Métriques de remplacement, par usage** :
- risque instantané → **CVaR (Expected Shortfall)** par EVT, § 2 ;
- risque de trajectoire → **CDaR** (moyenne des q % pires drawdowns), par bootstrap **par
  blocs** — le seul estimateur qui préserve le clustering de volatilité ;
- qualité de la distribution → **ratio de Rachev** (ES du gain à 95 % / ES de la perte à 95 %)
  et **oméga** : ils comparent des queues, pas des moments, donc restent définis pour
  `alpha > 1` ;
- pour classer des stratégies → **Sharpe déflaté** avec `n_eff` (cf. [[M2_LABELLISATION_CV]] § 4)
  et non `n`.

## 2. CVaR sous loi de puissance

Peaks-Over-Threshold : au-delà d'un seuil `u`, les excès suivent une GPD(xi, beta). Avec `n`
observations et `n_u` excès :

```
VaR_q = u + (beta/xi) · [ ( (n/n_u)·(1−q) )^(−xi) − 1 ]
ES_q  = ( VaR_q + beta − xi·u ) / (1 − xi)              valable pour xi < 1
```

Les deux formules sont **déjà correctes** dans `evt.py`. Ce qui doit changer est
l'**estimateur** : la méthode des moments actuelle suppose une variance finie des excès,
donc `xi < 0,5` — hypothèse fausse en crypto. Moments pondérés par les probabilités (formes
fermées, vérifiées analytiquement) :

```
excès triés CROISSANTS,  p_i = (i − 0,35)/n
a0 = moyenne(x_i)                a1 = moyenne( (1 − p_i)·x_i )

xi   = 2 − a0/(a0 − 2·a1)
beta = 2·a0·a1/(a0 − 2·a1)
```
(Pour une GPD(xi,beta) : `a0 = beta/(1−xi)`, `a1 = beta/(2(2−xi))`, d'où `a0/(a0−2a1) = 2−xi`.)

Trois pièges de mise en œuvre :
- **Choix du seuil `u`** : trop bas, la GPD ne s'applique pas ; trop haut, il ne reste rien.
  Le *mean excess plot* doit être approximativement linéaire au-dessus de `u` — condition à
  vérifier, pas à supposer. Défaut raisonnable : quantile 95 %, avec au moins 50 excès.
- **`xi ≥ 1`** : l'ES n'existe pas. Le renvoyer quand même serait une faute ; le code doit
  répondre « espérance de perte infinie sous ce modèle » et forcer une réduction d'exposition.
- **Pas d'échelle temporelle en racine.** `VaR_10j = sqrt(10)·VaR_1j` est faux hors gaussien.
  Estimer directement la GPD sur les pertes à h jours, ou bootstrapper par blocs.

## 3. Optimisation CVaR (spécifiée, non implémentée)

Rockafellar-Uryasev : minimiser la CVaR à niveau `q` est un **programme linéaire**, ce qui la
rend préférable à toute approche par simulation-recherche.

```
variables : w (poids), v (scalaire = VaR), u_s >= 0 (une par scénario s = 1..S)

minimiser   v + (1/(S·(1−q))) · somme_s u_s
sous        u_s >= −(r_s · w) − v          pour tout s
            u_s >= 0
            somme(w) = 1,  0 <= w <= w_max
            |B' w| <= epsilon              (neutralité factorielle, cf. M6/axe 2)
            espérance : mu' w >= r_cible
```

Deux exigences qui décident du résultat :
- **les scénarios `r_s`** doivent venir d'un bootstrap **par blocs** de l'historique réel,
  jamais d'un tirage gaussien — sinon on optimise une CVaR gaussienne, c'est-à-dire une
  variance déguisée ;
- **le nombre de scénarios** doit être grand devant `n/(1−q)`. À `q = 0,95`, chaque
  contrainte active repose sur 5 % des scénarios : 500 scénarios pour 50 actifs, c'est 25
  scénarios qui décident de tout. C'est le même problème de rang effectif qu'en [[M1_RMT_COVARIANCE]].

Dépendance : `scipy.optimize.linprog` (HiGHS) — le groupe `quant` de `pyproject.toml` déclare
déjà `scipy`. Non implémenté ici parce que non testable dans le conteneur ; c'est une
spécification, pas une livraison.

## 4. Kelly à queues épaisses — rappel opérationnel

`f* = argmax E[ln(1 + f·R)]` sur la distribution **empirique des round-trips réels**,
enrichie de la queue GPD, sous la borne de ruine `f < 1/|pire perte|`. La fraction se dérive
d'un budget de drawdown :

```
P(drawdown jusqu'à b·pic) = b^(2/lambda − 1)     ⇒     lambda = 2 / (1 + ln(eps)/ln(b))
```
`QUANT_DD_TARGET = 0,25` à 5 % de probabilité impose `lambda ≈ 0,175`, pas 0,25 (finding F10).

## 5. Coûts de financement : l'équation complète

```
r_net = r_brut
      − coûts_de_transaction                                  (spread + impact, M4)
      − (L − NAV)+ · r_marge · dt                             financement de la marge
      + S · (r_ref − frais_emprunt) · dt                      rebate (signe conservé)
      − dividendes_short · dt
      − marge_initiale · (hurdle − r_ref) · dt                 capital immobilisé
      + (NAV − L)+ · r_ref · dt                                cash oisif
```

Convention retenue (à écrire dans tout backtest, sinon deux résultats ne sont pas
comparables) : produits de la vente à découvert conservés en garantie (Reg-T), donc ils ne
réduisent pas la base de financement de la jambe longue.

**Ordres de grandeur mesurés** (NAV 1 M$, 365 jours, base 360) :
- levier 1,5× à 5,5 % → **−280 bps** de NAV par an, soit plus que l'alpha net de bien des
  stratégies « prometteuses » ;
- short 1 M$ à 0,5 % de frais d'emprunt et 4,5 % de taux de référence → **+405 bps** (rebate
  positif : la garantie rapporte) ;
- le même short sur un titre à 20 % de frais → **−1 570 bps**. L'écart entre les deux
  situations dépasse 19 % de NAV par an : c'est le paramètre le plus sensible de tout le
  système long-short, et il n'apparaît dans aucun backtest du dépôt.

**Le nombre à exiger du courtier avant d'ouvrir un short** :
```
frais_max = r_ref + (alpha_brut − coûts_de_transaction) / (S/NAV · dt)
```
Au-delà, le prêteur de titres capte l'edge. `max_borrow_fee()` le calcule ; à alpha
insuffisant, il renvoie 0 — ce qui se lit « ne pas ouvrir de short du tout ».

## 6. Pièges

- **Frais d'emprunt supposés constants** : ils sont revus quotidiennement et explosent
  précisément quand le short est le plus rentable (squeeze). Modéliser le pire cas, ou
  au minimum stresser à ×3 dans le sabotage-gate.
- **Rappel de titres (*buy-in*)** : le prêteur peut exiger la restitution. À traiter comme un
  stop forcé au pire moment, pas comme un aléa négligeable.
- **Coût du capital réglementaire ignoré** : sans lui, une stratégie à faible rendement mais
  forte marge paraît attractive alors qu'elle détruit de la valeur face au `hurdle`.
- **Intérêts composés sur les périodes courtes** : sur des robots 1 h, le portage se compte
  en fractions de point de base par barre — négligeable *par barre*, décisif *par an*.
  Comptabiliser au niveau du livre et par jour, jamais par trade.
