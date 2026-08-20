# M1 — Théorie des matrices aléatoires : stabiliser la covariance

Retour à [[18_MODULES_AVANCES]]. Code : `packages/portfolio/rmt_denoise.py`.

## 1. Le diagnostic avant le remède

Le seul nombre qui gouverne la fiabilité d'une covariance empirique est `q = n / T`
(n actifs, T observations). Trois conséquences, dans l'ordre de gravité :

- `q >= 1` : la matrice est **singulière**, de rang T au mieux. Toute inversion est une
  fiction numérique — et min-var, MVO, Black-Litterman inversent tous.
- `q` proche de 1 : la matrice est inversible mais les plus petites valeurs propres sont
  écrasées vers 0. Or l'optimiseur **charge précisément ces directions** : min-var maximise
  1/lambda. Il maximise donc l'erreur d'estimation. C'est la source mécanique de
  l'explosion des poids et du turnover, pas un défaut de « robustesse » vague.
- `q` petit (< 0,1) : régime confortable, mais alors la fenêtre est longue, donc la
  covariance est **stale** — on a échangé le bruit contre le retard.

Il n'existe pas de fenêtre qui échappe aux deux. Le débruitage est ce qui permet de
travailler à `q` intermédiaire sans payer l'un ou l'autre plein tarif.

## 2. La loi de Marčenko-Pastur

Pour une matrice de corrélation de n séries **indépendantes** de variance sigma², de T
observations, le spectre converge vers une densité à support borné :

```
lambda_± = sigma² · ( 1 ± sqrt(q) ) ²          q = n/T

densité(lambda) = sqrt( (lambda_+ − lambda)·(lambda − lambda_−) )
                  / ( 2·pi·sigma²·q·lambda )        sur [lambda_−, lambda_+]
```

Toute valeur propre **à l'intérieur** du support est indistinguable du bruit. C'est un
résultat asymptotique exact, pas une heuristique — d'où sa valeur comme critère.

Deux exigences d'application souvent violées :
- travailler sur la matrice de **CORRÉLATION**, jamais de covariance : la loi est
  adimensionnelle et suppose une trace égale à n ;
- utiliser le T des **observations effectives**, pas le nombre de lignes. Avec des
  rendements chevauchants (labels à barrière, moyennes mobiles), le T utile est celui de
  [[M2_LABELLISATION_CV]] § 4 : `effective_sample_size`.

## 3. Estimer sigma² : le point fixe, et sa limite

sigma² ne vaut pas 1 dès qu'il existe de vrais facteurs : ils absorbent une part de la
trace, donc le bruit résiduel est **plus petit** que 1. D'où l'itération :

```
sigma² ← 1
répéter :  k = #{ lambda_i > lambda_+(sigma²) }
           sigma² = moyenne des (n − k) valeurs propres restantes
jusqu'à stabilité de k
```

**Limite mesurée et documentée** (test `test_le_seuil_mp_seul_surdetecte_quand_les_facteurs
_dominent`) : quand quelques facteurs absorbent l'essentiel de la trace, les variances
idiosyncratiques deviennent hétérogènes après normalisation, le bulk s'élargit **au-delà**
du support MP, et le seuil sur-détecte — sur un modèle à 5 facteurs (n=60, T=400), `k_mp`
renvoie 15. Le seuil MP est donc une **borne supérieure**, pas une réponse.

Le complément qui tranche est l'**écart spectral** : parmi les `k_mp` candidats, retenir le
plus grand rapport `lambda_i / lambda_(i+1)`. Sur les modèles synthétiques à 1, 3 et 5
facteurs, il retrouve k **exactement**. Le module renvoie les deux (`k` et `k_mp`) : quand
ils divergent fortement, c'est une information sur la structure, pas un bug.

## 4. Débruiter, détoner, contracter — dans cet ordre

**Débruitage à valeur propre résiduelle constante** (López de Prado) :

```
garder lambda_1 .. lambda_k
remplacer lambda_(k+1) .. lambda_n  par leur MOYENNE
C_debruitee = V · diag(lambda') · V'          puis re-normaliser la diagonale à 1
```

La moyenne — et non zéro, et non un seuillage — préserve la **trace**, donc la variance
totale du portefeuille. Un seuillage à zéro rendrait la matrice singulière et ferait croire
à une diversification infinie dans les directions supprimées.

**Détonage** (retrait du premier facteur) : utile pour le *clustering* et l'étude de
structure. Interdit pour le dimensionnement : sur une matrice détonée, la corrélation
moyenne s'effondre et un optimiseur y verrait une diversification qui n'existe pas. Le
module l'expose, la docstring l'interdit explicitement.

**Contraction de Ledoit-Wolf** ensuite, pas avant. Les deux opérations ne font pas la même
chose : le débruitage corrige la **structure** du spectre, la contraction rapproche la
matrice d'une **cible** (ici corrélation constante — meilleure que l'identité pour des
actions, qui partagent un facteur marché). L'implémentation existante
(`packages/data/engine.py:ledoit_wolf_shrinkage`) est correcte et estime l'intensité
`delta` sur les données ; `denoise_covariance` la réutilise plutôt que de la redéfinir.

## 5. Ce que le diagnostic doit interdire

`denoise_covariance` renvoie un **verdict**, et c'est lui qui doit gouverner l'appelant :

| Situation | Conduite |
|---|---|
| `k_signal < 2` | Aucune optimisation transversale. Une seule direction fiable = équipondération ou risk-parity sur volatilités seules, pas de matrice. |
| `q > 0,5` | Fenêtre trop courte. Allonger, ou réduire l'univers, ou passer à une covariance à facteurs (n·k paramètres au lieu de n²/2). |
| `cond_after` toujours > 10⁴ | Colinéarité structurelle (deux ETF quasi identiques, une action et son ADR). Dédupliquer AVANT d'estimer. |
| Historiques de longueurs inégales | **Ne jamais** compléter par zéro : cela crée une corrélation artificielle nulle. Tronquer à l'intersection, ou estimer par paires puis projeter sur le cône semi-défini positif. |

## 6. Pièges d'implémentation

- **Non-stationnarité** : estimer sur des rendements, jamais des niveaux, et vérifier que
  la fenêtre ne chevauche pas un changement de régime documenté (mars 2020 dans une fenêtre
  de 2 ans contamine tout).
- **Corrélation de Pearson sur queues épaisses** : un seul jour extrême commun crée une
  corrélation de 0,8 entre deux actifs indépendants. Sur les fenêtres courtes, préférer
  Spearman ou Kendall, puis convertir (`rho_Pearson ≈ sin(pi·tau_Kendall/2)`), et
  re-projeter sur le cône semi-défini positif.
- **EWMA** : pondérer les observations récentes réduit le T **effectif** à
  `(1+lambda)/(1−lambda)` observations équivalentes. Un EWMA à 0,97 sur 500 jours n'a pas
  500 observations mais ~66 : recalculer `q` avec ce T-là, sinon le diagnostic ment.
- **Johansen pour les paniers** : quand la cointégration porte sur plus de deux actifs, le
  test de la trace de Johansen repose sur la décomposition en valeurs propres généralisées
  de matrices de covariance résiduelles — donc exactement sur les objets débruités ici. À
  implémenter APRÈS M1, jamais avant : un Johansen sur covariance bruitée trouve des
  relations de cointégration inexistantes, avec la même mécanique que le sur-comptage MP.
