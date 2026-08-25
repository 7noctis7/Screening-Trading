# Journal des décisions

> Décisions structurantes prises pendant la mission de finalisation et de passation.
> L'archive complète des ADR du projet reste dans `vault/02_DECISIONS.md` ; ce fichier est la
> version publique et n'en est pas un doublon : il ne contient que les décisions de cette phase.

---

**Date** : 2026-08-25
**Décision** : insérer un portail de risque **par ordre** dans le chemin de production, plutôt que
d'y brancher `RiskEngine`.
**Contexte** : `RiskEngine` (règles reward/risk, nombre de positions, exposition par actif) n'était
instancié que dans `scripts/demo_*.py`. Le chemin de production, `scripts/run_live.py`, envoyait au
courtier le montant décidé par la stratégie, mis à l'échelle par le seul facteur du kill-switch.
Les limites de risque du projet étaient documentées, testées, et absentes de la seule chaîne qui
envoie de vrais ordres.
**Alternatives** : (a) brancher `RiskEngine` tel quel sur `run_live.py` ; (b) écrire un portail
minimal dédié ; (c) ne rien faire et documenter le trou.
**Choix** : (b).
**Pourquoi** : `RiskEngine` raisonne par signal et par stop, barre par barre, en streaming.
`run_live.py` réconcilie un portefeuille cible en une passe : il n'a ni signal, ni stop, ni barre.
Le brancher aurait exigé de fabriquer des objets `Order` et `signal` factices pour satisfaire une
interface conçue pour autre chose — et un adaptateur factice au milieu d'une barrière de sécurité
est précisément ce qu'on ne veut pas. Le portail voit un ordre, un état de compte et des limites
lues dans l'environnement : cette pauvreté d'interface est ce qui le rend non contournable.
**Conséquences** : deux couches de risque coexistent désormais, avec des périmètres distincts.
`RiskEngine` reste hors production — c'est un P1 assumé et documenté (`docs/ROADMAP.md` P1-1), pas
un oubli. Les règles de stop et de reward/risk ne s'appliquent toujours pas au rebalancement.

---

**Date** : 2026-08-25
**Décision** : dans le portail, un désengagement passe **avant** le contrôle d'equity.
**Contexte** : la première version refusait tout ordre quand l'equity était nulle ou illisible, au
nom du principe « inconnu ≠ zéro » qui régit le reste du dépôt. Un test que j'avais écrit figeait
ce comportement.
**Alternatives** : (a) garder le refus systématique ; (b) laisser passer les seuls désengagements.
**Choix** : (b).
**Pourquoi** : une liquidation part en **quantité**, pas en montant — elle n'a pas besoin qu'on
sache dimensionner. Refuser une sortie parce que le courtier n'a pas renvoyé l'equity enferme la
position le jour précis où l'on veut sortir. C'est la même erreur que le plancher de ligne qui ne
gardait que les ouvertures : une règle correcte appliquée dans un seul sens produit l'inverse de
son intention.
**Conséquences** : le test a été réécrit pour affirmer le comportement correct. Un achat reste
refusé si l'equity est illisible.

---

**Date** : 2026-08-25
**Décision** : la watchlist X est livrée avec **zéro compte authentifié** et **aucun nombre
d'abonnés**.
**Contexte** : 66 comptes fournis par le propriétaire du projet, à intégrer dans une couche dont
la fonction est précisément de pondérer la fiabilité des sources.
**Alternatives** : (a) renseigner les statuts de vérification et les nombres d'abonnés depuis la
connaissance du modèle ; (b) tout livrer non vérifié avec une procédure d'authentification.
**Choix** : (b).
**Pourquoi** : renseigner ces champs sans les avoir relevés produirait exactement le défaut que
toute la couche existe pour empêcher — une donnée fabriquée présentée comme un fait. Un nombre
d'abonnés de 2024 mémorisé par un modèle n'est pas une mesure.
**Conséquences** : les 66 comptes sont plafonnés à 0,60 de crédit et aucun n'est utilisable seul
sur une information à impact. `a_verifier()` renvoie les 66 et restera bruyante jusqu'à ce que
quelqu'un fasse le travail. Un handle (`"Jensen Huang"`) est un **nom** et n'est pas résoluble :
il est signalé comme tel plutôt que deviné.

---

**Date** : 2026-08-25
**Décision** : le test de séparation architecturale inspecte l'**arbre syntaxique**, pas le texte.
**Contexte** : la première version vérifiait que la chaîne `packages.execution` n'apparaissait pas
dans les fichiers de `packages/intelligence`. Elle échouait sur les commentaires qui expliquent
justement l'interdiction.
**Choix** : parser les fichiers avec `ast` et n'examiner que les nœuds `Import` / `ImportFrom`.
**Pourquoi** : un test qui confond une mention et un import ne teste pas l'architecture, il teste
la prose. Il aurait par ailleurs poussé à retirer les commentaires qui documentent la règle.
**Conséquences** : le test assure aussi qu'au moins un module a été trouvé — sinon il passerait
sur un répertoire vide sans rien prouver.

---

**Date** : 2026-08-25
**Décision** : un candidat long-only doit battre la détention équipondérée de l'univers.
**Contexte** : le labo d'alpha promouvait deux hypothèses en long-only (Sharpe 1,70, DSR 94 %,
placebo 0,000) sans point de comparaison. Les mêmes signaux, même période et même exécution,
donnaient un Sharpe long/short entre −1,28 et +0,76. L'une des hypothèses promues avait un IC de
+0,0064 pour un t-stat de +0,27 — aucun pouvoir prédictif transversal.
**Choix** : ajouter un benchmark équipondéré sur la même grille, publier bêta / alpha / IR
d'excès, et refuser un candidat long-only dont l'alpha ou l'IR d'excès est négatif.
**Pourquoi** : ce n'est pas un seuil de performance discutable mais un gate de pertinence. Une
stratégie long-only qui fait moins bien que l'équipondéré du même univers est une façon coûteuse
d'acheter le marché.
**Conséquences** : des candidats précédemment promus seront probablement rejetés au prochain run.
C'est l'objectif.

---

**Date** : 2026-08-25 (soir)
**Décision** : `RiskEngine` reste réservé au moteur événementiel ; le rééquilibrage garde
`order_gate` comme seule barrière.
**Contexte** : deux couches de risque coexistaient sans se rencontrer. `order_gate` a été branché
sur le chemin de production le matin ; les règles de stop et de reward/risk de `RiskEngine`
restaient hors circuit.
**Alternatives** : (A) déclarer `RiskEngine` réservé au streaming et l'écrire ; (B) le brancher
sur `run_live.py` via un adaptateur.
**Choix** : (A).
**Pourquoi** : `RiskEngine.approve(order, positions, equity, regime, signal)` suppose un ordre
unitaire, le signal qui l'a produit et le stop qui le borne. Le rééquilibrage n'a aucun des
trois : il réconcilie un portefeuille cible en une passe. Fabriquer des objets factices pour
satisfaire l'interface placerait un adaptateur fictif au cœur d'une barrière de sécurité, et
produirait deux vérités sur le risque là où il en faut une.
**Conséquences** : les règles de stop et de reward/risk ne s'appliquent toujours pas au
rééquilibrage — c'est assumé, pas oublié. Le périmètre est écrit dans le module lui-même, et
quatre tests d'architecture le fixent. Si quelqu'un branche `RiskEngine` un jour, il devra
retirer un test et mettre à jour cet ADR : ce sera délibéré.

---

**Date** : 2026-08-25 (soir)
**Décision** : la courbe, le journal de trades et le ledger sont alignés par date sur une grille
**sans NaN**, et non sur la matrice à NaN du backtest.
**Contexte** : ces trois fonctions prenaient les dates d'UNE série de référence et supposaient
que les autres partageaient son calendrier. Avec des actions et des cryptos dans le même panier,
cette supposition décalait les colonnes de plusieurs années.
**Alternatives** : (a) leur apprendre à gérer les NaN comme `preset_backtest` ; (b) leur donner
une grille garantie sans NaN.
**Choix** : (b).
**Pourquoi** : le ledger fait de la comptabilité parts/cash. Un NaN mal géré y produit un P&L
**faux** — pas une exception, pas un avertissement : un chiffre crédible et erroné. Le coût de
(b) est une grille plus étroite ; le coût de (a) est un risque de fausseté silencieuse dans la
seule fonction censée justifier la performance affichée.
**Conséquences** : la fenêtre peut être plus courte quand une série a des trous. `fenetre_par_rang`
devient du code mort et est retiré.
