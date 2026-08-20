# AXE 4 — Dimensionnement des positions & contrôle des frictions

Retour à [[17_AUDIT_INSTITUTIONNEL]].
Code livré : `packages/execution/impact.py`, `packages/portfolio/sizing/kelly_fat_tail.py`.

## 1. Pourquoi le Kelly actuel surestime la mise

`packages/portfolio/sizing/kelly_uncertain.py` résout `f = p − (1−p)/b` : deux issues, une
perte unique et bornée. Sur une distribution réelle à queue gauche continue, cette borne
n'existe pas, et le rétrécissement porte seulement sur `p`. Trois défauts cumulés :
asymétrie ignorée, queue ignorée, fraction 0,25 posée par convention plutôt que dérivée.

### Formulation correcte
```
f* = argmax_f  E[ ln(1 + f·R) ]          sous  f < 1 / |pire perte|
```
Procédure (implémentée dans `kelly_fat_tail.py`) :
1. Construire `R` à partir des **round-trips réels** (`data/journal.db`, `legacy=0`), jamais du
   backtest — les fills du backtest sont ceux du modèle, pas ceux du marché. `N < 50` ⇒ **UNCALIBRATED**.
2. **Enrichir la queue gauche** par tirage dans la GPD ajustée (`portfolio/evt.py`, corrigée
   PWM cf. [[AXE3_QUEUES_REGIMES]] § 1.2). Sans cela, la pire perte de l'échantillon borne `f*`
   trop haut : le pire est toujours devant.
3. Maximiser par section dorée (la fonction est concave) sur `[0, 0,999/|pire perte|]`.

### Choisir la fraction par un budget de drawdown, pas par superstition
Pour un MBG, une stratégie à la fraction `lambda` du Kelly complet touche un jour la fraction
`b` de son pic avec la probabilité
```
P(drawdown jusqu'à b·pic) = b ^ (2/lambda − 1)
```
d'où, en inversant :
```
lambda = 2 / ( 1 + ln(eps) / ln(b) )
```

| Budget | b | eps | lambda | Lecture |
|---|---|---|---|---|
| DD 50 % toléré à 1 % | 0,50 | 0,01 | **0,26** | le « quart de Kelly » classique, enfin **dérivé** |
| **DD 25 % (`QUANT_DD_TARGET`) à 5 %** | 0,75 | 0,05 | **0,175** | ≈ **1/6 de Kelly** |
| DD 25 % à 1 % | 0,75 | 0,01 | **0,118** | ≈ 1/8,5 de Kelly |
| Kelly complet | 0,50 | — | 1,00 | **50 % de chances** de perdre la moitié du capital |

Conséquence directe pour ce dépôt : la valeur par défaut `fraction=0.25` de
`kelly_uncertain.sized_kelly` est **cohérente avec un budget de drawdown de 50 %**, pas avec
le `QUANT_DD_TARGET=0.25` affiché ailleurs. Les deux réglages disent des choses différentes du
même appétit pour le risque. Il faut trancher, et le faire une seule fois.

⚠️ La formule est **brownienne** : elle est *optimiste* sous queues épaisses. Ne pas inventer
un facteur de correction — **vérifier** par bootstrap par blocs (le simulateur Monte-Carlo du
front et `mc_projection` font déjà exactement ce travail) et retenir le `lambda` le plus
prudent des deux méthodes.

---

## 2. Superposer les contraintes de taille (ordre imposé, pas négociable)

```
taille = min(
    Kelly fractionnaire        f_used = lambda · f*                    (croissance)
    cible de volatilité        gross = vol_cible / vol_prévue          (existant)
    budget CVaR                gross ≤ CVaR_budget / CVaR_99(gross=1)  (à ajouter)
    plafond de participation   q ≤ POV · volume_fenêtre                (impact.py)
    budget de coût             q ≤ max_qty_for_budget(...)             (impact.py)
    plafonds de concentration  nom / secteur / indice                  (risk/limits.py)
)
```
Le **budget CVaR** est la pièce manquante et elle répare un défaut connu du vol-targeting : la
taille augmente quand la volatilité est basse — c'est-à-dire exactement quand les queues sont
les plus épaisses et le levier implicite le plus dangereux. `portfolio/evt.py` fournit déjà la
CVaR ; il ne manque que le plafonnement.

---

## 3. Fonction d'impact de marché (correctif F2)

Le forfait en bps de `costs.py` facture pareil un ordre à 0,1 % de l'ADV et un ordre à 20 %.
Modèle à substituer (Almgren-Chriss, Torre/BARRA — consensus buy-side) :

```
impact_bps = Y · sigma_fenêtre_bps · ( Q / V_fenêtre ) ^ psi         psi ≈ 0,5
coût_aller_bps = demi_spread + frais + impact_bps
```

Les deux erreurs qui rendent ce modèle faux quand on l'applique en intraday :
- **la volatilité doit être celle de la fenêtre d'exécution** :
  `sigma_fenêtre = sigma_jour · √(minutes / minutes_séance)` ;
- **le volume aussi** : sur une barre 1 h d'une séance de 6 h 30, `V ≈ ADV/6,5`, jamais l'ADV.
  Utiliser l'ADV sur une barre horaire divise l'impact estimé par ~2,5.

Inversion utile — la taille maximale sous budget de coût :
```
Q* = V_fenêtre · ( (budget_bps − demi_spread − frais) / (Y · sigma_fenêtre_bps) ) ²
```
et le plafond dur, indépendant du budget : `Q ≤ POV · V_fenêtre` (POV 10 % en régime normal,
5 % en stress). Les deux sont implémentés (`max_qty_for_budget`, `participation_cap`).

### Calibrer Y sur tes propres fills (ne pas croire 0,8)
`packages/execution/tca.py` mesure déjà l'*implementation shortfall* et
`research/exec_costs.py` le slippage réel décision→fill. Régresser, sans constante :
```
slippage_réalisé_bps  ~  sigma_fenêtre_bps · √(Q / V_fenêtre)        → la pente est Y
```
`N < 100` fills ⇒ **UNCALIBRATED**, on garde `Y = 0,8` comme *a priori prudent* **et on l'écrit**.
Régresser avec la constante donne en prime une estimation du demi-spread effectif payé.

### Capacité
Avec une rotation annuelle `tau` et un budget de coût `c_max` (bps de NAV), la capacité
d'une stratégie croît comme
```
AUM_max  ∝  ADV · ( c_max / (Y · sigma) ) ² / tau
```
`packages/portfolio/capacity.py` existe : c'est le bon endroit pour brancher cette formule et
répondre à « jusqu'à quelle taille cette stratégie survit-elle ? » — question qu'un comité pose
toujours, et à laquelle le dépôt ne sait pas répondre aujourd'hui.

### Bande de non-trading (finding F8)
La bande en dur de `preset_backtest` a une forme théorique :
`largeur ∝ (coût / alpha) ^ (1/3)` (Constantinides ; Garleanu-Pedersen).
Seule la **forme** est théorique — la constante d'échelle dépend de l'aversion au risque et
doit être calibrée. `impact.no_trade_band` code la forme et signale explicitement que le
niveau est un placeholder.

---

## 4. Le test d'admission : la question à poser avant d'écrire un robot

```
alpha_attendu_bps  >  k · coût_aller_retour_bps          k ≥ 2
```
(`impact.admit_signal`). Avec `k = 1`, on trade l'espérance nulle de Bachelier en payant le
spread : la ruine est lente mais certaine. `k = 2` laisse une marge pour l'erreur d'estimation
de l'alpha, qui est toujours plus grande que celle du coût.

### 4.5 L'arithmétique qui décide des timeframes 1 h / 4 h
En combinant `alpha(h) = sigma(h)·IC·z` (axe 2) avec le test d'admission, l'horizon minimal
viable se déduit en fermé :

```
h_min  =  ( k · coût_aller_retour_bps / ( IC · z · sigma_1barre_bps ) ) ²      [en barres]
```

Application aux **barèmes réellement configurés** dans `packages/execution/costs.py`
(hypothèses de signal : `IC = 0,05` crypto / `0,03` actions, `z = 2`, `k = 2` — à **mesurer**,
statut UNCALIBRATED) :

| Terrain | Coût aller-retour | sigma 1 h | alpha 1 h | Horizon minimal viable |
|---|---|---|---|---|
| Actions US (Alpaca, 5 bps aller) | ~10 bps | ~59 bps | ~3,5 bps | **≈ 34 h ≈ 1 semaine** |
| Crypto (Binance, 20 bps aller) | ~40 bps | ~100 bps | ~10 bps | **≈ 64 h ≈ 2,7 jours** |
| Crypto (**BitMart, 37 bps aller**) | ~74 bps | ~100 bps | ~10 bps | **≈ 219 h ≈ 9 jours** |

Trois conclusions, et elles sont dures :
1. **Aucun robot 1 h ou 4 h ne passe l'admission avec les courtiers configurés.** Le problème
   n'est pas le signal : à IC = 0,05, il faudrait `IC ≈ 0,74` chez BitMart pour rentabiliser
   une détention d'une heure — soit dix fois ce que produit la meilleure littérature.
2. Le levier le plus rentable n'est **pas** un meilleur signal, c'est **un meilleur coût** :
   passer de BitMart à Binance divise l'horizon minimal par 3,4. Exécuter en **maker**
   (limites passives, 0 à 2 bps) plutôt qu'en taker le divise encore. C'est la seule voie
   crédible vers l'intraday — et elle exige le simulateur de file d'attente de l'[[AXE5_EXECUTION]].
3. Les horizons **Daily / Weekly / Monthly** sont, eux, largement au-dessus du seuil : c'est
   cohérent avec le fait que le dépôt y ait déjà trouvé quelque chose de mesurable.

Ce tableau est à **refaire avec ton IC mesuré** dès que `alpha_decay` tourne sur données
réelles. Tant que l'IC est supposé, ces horizons sont des ordres de grandeur — mais l'ordre de
grandeur suffit déjà à trancher la question du 1 h.

---

## 5. Pièges de dimensionnement à ne pas régresser

- **Kelly sur des rendements de backtest** : le backtest ne contient pas les fills manqués ni
  les jours où le courtier était injoignable. Toujours sur le journal réel.
- **Kelly par stratégie puis somme** : les stratégies partagent les mêmes chocs. Le Kelly
  multivarié (`f* = Sigma⁻¹ · mu`) est le bon objet, et il exige une covariance rétrécie.
  À défaut, appliquer Kelly au **livre consolidé** puis répartir.
- **Vol-targeting sans plafond de levier** : une vol prévue proche de zéro renvoie un gross
  infini. Le `min(1.0, ...)` de `preset_backtest` protège aujourd'hui — ce n'est pas un détail,
  c'est ce qui empêche l'accident, et il doit être testé comme tel.
- **Coût facturé par barre plutôt que sur |Δposition|** : corrigé en juillet (M-2), à ne pas
  régresser en réintroduisant un coût forfaitaire par pas.
- **Impact ignoré à la sortie** : liquider en stress coûte 2 à 5 fois l'impact d'entrée
  (la volatilité de la fenêtre explose et le volume s'évapore simultanément). Le scénario de
  stress doit facturer une liquidation à `Y·3` et POV 5 %, pas au coût normal.
