# 20 — Comment les institutions produisent réellement de l'alpha (2026-08-20)

> Question posée : « comment font Citadel, Goldman, JPMorgan, Pictet, UBS, les family offices
> et les hedge funds ? » Première réponse, et elle conditionne tout le reste : **ils ne font
> pas le même métier**. Les confondre est l'erreur qui fait perdre le plus de temps.

## 1. Quatre métiers distincts, quatre sources de revenu

### Banques d'investissement — Goldman Sachs, JPMorgan
L'essentiel de leurs revenus de marché **n'est pas de l'alpha directionnel** :
- **tenue de marché** : capture du spread bid-ask sur un flux client massif, internalisation
  des ordres (on croise deux clients sans jamais toucher le marché) ;
- **financement** : prime brokerage, prêt de titres, repo — un revenu de bilan, pas de vue ;
- **structuration** : vendre de la convexité empaquetée, en gardant la marge de modèle.

Leur avantage est **structurel** : bilan, flux client, licence. Il n'est pas réplicable, et
aucune quantité de talent quantitatif ne le remplace. **Rien à copier ici**, sinon la
discipline de mesure du coût d'exécution.

### Banques privées — Pictet, UBS
Très peu d'alpha au sens strict. Leur métier : allocation d'actifs, sélection de gérants,
optimisation fiscale, accès à des classes illiquides, et — le plus sous-estimé —
**accompagnement comportemental** (empêcher le client de vendre au plus bas). La
« surperformance » vendue est majoritairement de la gestion du risque et de la fiscalité,
plus une capture de frais.

**Transférable** : la discipline d'allocation, et l'idée que ne pas faire d'erreur vaut plus
que d'avoir raison.

### Multi-stratégies — Citadel, Millennium, Point72
Le modèle en **pods**. Cent à deux cents équipes, chacune avec :
- un Sharpe individuel **modeste** (0,7 à 1,2 — pas 3) ;
- des contraintes de risque très serrées (coupure à −5 %, neutralité factorielle imposée) ;
- et surtout une **décorrélation imposée** avec les autres pods.

Le Sharpe du fonds (3 à 5) ne vient d'aucun génie individuel : il vient de **l'agrégation de
paris faibles et décorrélés**, plus un levier à taux institutionnel (4 à 8×) que seule la
décorrélation rend supportable. S'y ajoutent une infrastructure d'exécution et une dépense en
données de l'ordre de 100 M$/an.

**Transférable — et c'est le cœur** : agréger beaucoup de signaux faibles peu corrélés, sous
contrainte de risque serrée, bat systématiquement la recherche du signal fort unique.

### Quants purs — Renaissance (Medallion), TGS, DE Shaw
Des centaines de signaux faibles, horizon court, et une **capacité volontairement limitée**
(Medallion est fermé aux capitaux extérieurs : leur edge ne passe pas à l'échelle). Edge =
données + vitesse + nombre de signaux + petitesse assumée.

**Transférable** : la logique de souffle. **Non transférable** : la vitesse et la dépense data.

### Family offices
Leur avantage n'est ni la vitesse ni le signal : c'est **l'horizon et l'absence de rachats**.
Ils encaissent la prime d'illiquidité (private equity, immobilier, dette privée,
co-investissements) que personne soumis à des rachats trimestriels ne peut porter. Plus la
fiscalité et la transmission.

**Transférable — et c'est le second point clé** : l'horizon long est le seul avantage
structurel dont dispose un particulier. Il ne coûte rien et personne ne peut te le prendre.

---

## 2. Les cinq mécanismes réels de l'alpha

Sous les habillages, tout revient à cinq sources. Il n'y en a pas de sixième.

| # | Mécanisme | Exemple | Accessible en solo ? |
|---|---|---|---|
| 1 | **Prime de risque** portée par d'autres | value, carry, vente de volatilité | **Oui** — mais c'est du bêta exotique, à nommer comme tel |
| 2 | **Contrainte des autres** | rebalancement d'indices, fin de trimestre, appels de marge, mandats interdisant certains titres | **Oui**, et c'est le terrain le plus sous-exploité |
| 3 | **Information supérieure** | données alternatives, recherche fondamentale profonde, réseau | Non — coût prohibitif |
| 4 | **Vitesse** | microstructure, colocation | Non |
| 5 | **Capacité de porter le risque** que d'autres refusent | illiquidité, événements binaires, drawdowns longs | **Oui** — c'est l'avantage du family office |

Un opérateur seul joue **1, 2 et 5**. Prétendre jouer 3 et 4 avec un Mac et yfinance est la
façon la plus rapide de perdre de l'argent en croyant faire de la science.

---

## 3. Ce que cela impose à ce projet

### La cible réaliste, chiffrée
Un bon gérant actions long/short affiche un **IR net de 0,4 à 0,7**. Pas 3. Avec
`IR = IC·√BR·TC` : 300 noms, 12 rebalancements par an, IC combiné de 0,05 et un coefficient de
transfert de 0,5 donnent un **IR plafond d'environ 1,2** — dont il faut retrancher les coûts,
les frictions et l'erreur d'estimation. Viser 0,5 net est ambitieux ; viser 2 est une fiction.

### L'architecture qui en découle
1. **Cœur = bêta géré.** Déjà en place, et c'est le meilleur actif du projet : un Calmar de
   5,4 contre 0,17 est un vrai résultat. Ce n'est pas de l'alpha, c'est du risque bien géré —
   ce qui se vend, à condition de le nommer honnêtement.
2. **Satellite = combinaison de facteurs publics** sur univers large, neutralisée des
   expositions factorielles, risque serré. C'est la transposition du modèle en pods à une
   seule personne : `make alpha-lab` le fait désormais.
3. **Terrain de chasse = mécanisme 2.** Rebalancements d'indices annoncés à l'avance,
   effets de fin de mois, PEAD sur small caps, décotes de holdings, crypto (moins saturée).
   Tout ce qui vient d'une contrainte et non d'une opinion.
4. **Horizon = mécanisme 5.** Ne pas concurrencer les pods sur leur terrain (jours à semaines)
   quand on peut tenir six mois sans rendre de comptes.

### Ce qui ne marchera pas, et qu'il faut cesser d'essayer
- Momentum quotidien long-only sur mégacaps US : le coin le plus concurrencé de la finance.
- Chercher LE signal à IC 0,15. Il n'existe pas dans les données publiques.
- Battre quiconque sur la latence ou la dépense en données.

---

## 4. Le seul avantage compétitif défendable ici

Ni la vitesse, ni les données, ni le capital. **L'intégrité de la mesure.**

La quasi-totalité des acteurs non institutionnels — et une bonne partie des institutionnels —
ne savent pas si leur backtest vaut quelque chose. Ce dépôt le sait : gate à quatre étages,
ledger qui déflate le Sharpe par le nombre d'essais, point-in-time vérifié par sentinelle,
validation croisée purgée et combinatoire, unicité d'échantillon, diagnostic d'exploitabilité
de la covariance.

C'est ce qui permet de ne pas mettre de capital sur du bruit — ce qui, sur dix ans, vaut plus
que la plupart des alphas revendiqués. Et c'est aussi, si le sujet du produit revient, la
seule chose ici qu'un tiers paierait.
