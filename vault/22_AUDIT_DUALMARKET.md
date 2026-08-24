# 22 — Audit DualMarketScreening (2026-08-22)

Revue du moteur d'arbitrage statistique (`quant/coint.py`, `quant/research/`), à la demande de
l'utilisateur. Code lu, pas supposé.

---

## Ce qui est déjà juste — et qui est rare

Un audit qui ne trouve que des problèmes n'a pas regardé. Quatre choses sont faites correctement,
et trois d'entre elles sont ratées par la plupart des implémentations publiées :

**Les bonnes valeurs critiques.** `ADF_CV_EG = {-3.90, -3.34, -3.04}` au lieu des valeurs ADF
standard, avec le commentaire qui explique pourquoi : le test porte sur un résidu **estimé**, sa
distribution est décalée, et ignorer ce décalage accepte environ deux fois trop de paires.

**La correction de Kendall** sur le biais de petit échantillon du MCO en AR(1) :
`φ̂ + (1+3φ)/n`. Sans elle, θ est surestimé, donc la demi-vie sous-estimée — on sort trop tôt.

**Le z-score de Kalman sans look-ahead.** L'innovation `e_t` et sa variance `Q_t` n'utilisent que
l'information en t−1. C'est le point décisif face à un z-score MCO plein échantillon, où β a vu
tout le futur.

**`optimal_band` maximise un TAUX de profit**, pas un profit par trade : `g(u) = (2u·σ_eq − c) /
E[T(u)]`, avec le temps moyen de premier passage de l'OU. Un seuil haut gagne plus par trade mais
échantillonne moins souvent. « 2σ par convention » est un choix non argumenté ; celui-ci ne l'est
pas.

---

## Trois défauts, par gravité

### P0 — Aucune correction pour tests multiples

Zéro occurrence de Bonferroni, FDR ou Benjamini-Hochberg dans `quant/`.

Cribler N paires et retenir celles dont `p < 0,05` produit **5 % de faux positifs par
construction**. Sur 100 paires candidates, cela fait environ cinq verdicts « tradable » qui ne
sont que du bruit — et rien ne les distingue des vrais.

L'ironie est instructive : le code corrige scrupuleusement un biais d'un facteur ~2 (valeurs
critiques EG contre ADF) et laisse ouvert un biais d'un facteur ~5 sur un criblage de 100 paires.
Le second est plus grand que le premier.

**Correctif.** Benjamini-Hochberg plutôt que Bonferroni : sur des paires corrélées entre elles,
Bonferroni est si conservateur qu'il ne laisse rien passer. BH contrôle la proportion attendue de
fausses découvertes parmi les retenues, ce qui est la bonne question ici. Et **publier le nombre
de paires testées** avec le verdict : un « tradable » issu d'un criblage de 500 paires ne vaut pas
le même issu de 5.

### P0 — Le coût est un scalaire, alors que le portage dépend du TEMPS

`optimal_band(theta, sigma_eq, cost, ...)` reçoit `cost` comme un coût d'aller-retour **fixe**.

Sur une détention de 2 à 8 jours en perpétuels, ce n'est pas la friction d'exécution qui domine :
c'est le **funding**, prélevé toutes les huit heures, variable, et **de signe changeant**. Un
spread dont l'espérance brute est positive peut être négatif net de portage — et rien dans le
modèle actuel ne peut le détecter, puisque le coût ne dépend pas de la durée.

Même chose côté actions : *borrow fee* sur la jambe vendue, dividendes détachés pendant la
détention.

**Correctif, et il est court** : le coût doit s'écrire `c(u) = c_fixe + c_portage × E[T(u)]`.
`E[T(u)]` est **déjà calculé** par `ou_mfpt` à la ligne suivante. La modification tient en un
terme, et elle change la nature du résultat : le seuil optimal cesse d'être un compromis
gain/fréquence pour devenir un compromis gain/fréquence/**durée d'exposition au portage**. Sur
une paire à demi-vie longue et funding défavorable, `optimal_band` doit renvoyer `None`.

### P1 — La calibration du Kalman voit tout l'échantillon

`kalman_calibrate(y, x)` cherche (δ, r) par maximum de vraisemblance **sur toute la série**.

Le z-score est ensuite sans look-ahead *étant donné* (δ, r) — mais (δ, r) a vu le futur. Le filtre
est donc réglé avec une information qui n'était pas disponible au moment des décisions qu'il
produit. Le biais est subtil, il ne casse rien, et il gonfle la performance mesurée.

**Correctif.** Calibrer sur une fenêtre d'apprentissage seule, ou en fenêtre glissante
ré-estimée périodiquement. Le coût est un peu de performance affichée en moins ; c'est la
différence entre un résultat et un résultat vrai.

*Note.* Le brief demandait des matrices Q/R **adaptatives** face aux chocs de volatilité. Je ne
le recommande pas en priorité : rendre R adaptatif ajoute des degrés de liberté à un système qui
manque déjà de preuve. Corriger d'abord le look-ahead de calibration ; l'adaptativité viendra
après, si les faits la réclament.

---

## Ce que je NE recommande pas

**FinRL / apprentissage par renforcement.** Sur un horizon de 2 à 8 jours, avec un DSR proche de
zéro, ajouter de l'apprentissage profond par renforcement multiplie les degrés de liberté là où
le problème est le manque de preuve. Le RL brille quand les données sont abondantes et le signal
net ; ici, ni l'un ni l'autre.

**QRL (quantum reinforcement learning).** Aucun apport identifiable sur ce problème. C'est le cas
d'école de l'over-engineering : la complexité y est visible, le gain non mesurable.

**TA-Lib.** Ferait doublon avec `quant/metrics.py`, qui est en stdlib pure — une qualité qu'on
perdrait en ajoutant une dépendance C.

## Ce que je recommande, par ordre

1. **CCXT** — remplace les adaptateurs d'échange écrits à la main, et surtout **donne accès aux
   funding rates et à l'open interest**, sans quoi le correctif P0 ci-dessus n'a pas de données.
2. **Benjamini-Hochberg** sur le criblage de paires (une centaine de lignes, testable).
3. **Coût dépendant de la durée** dans `optimal_band` (un terme).
4. **OpenBB** pour SEC EDGAR et l'obligataire, si le besoin se confirme.
