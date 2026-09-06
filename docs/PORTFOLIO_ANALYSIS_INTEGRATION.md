# Analyse de portefeuille — contrat d'intégration

## Verdict actuel

La route `/analyse-portefeuille` livre l'import, la confirmation et le snapshot local. Une première
projection read-only joint ce snapshot aux scores de screening, fondamentaux, résultats, ML et à la
macro. En local, `POST /api/portfolio/analyze` charge désormais les historiques de l'univers exact,
aligne leurs dates sans remplissage, calcule le risque et recalcule min-variance/ERC/HRP. La conversion
FX multi-devises et l'optimisation dynamique par rendement attendu restent à raccorder.
projection read-only joint désormais ce snapshot aux scores de screening, fondamentaux, résultats,
ML et à la disponibilité macro déjà publiés par l'API. Les historiques complets, la conversion FX
et le recalcul d'allocations propres à l'univers importé restent à raccorder.

## Réutilisation prévue du système existant

| Preuve | Source existante | Usage autorisé dans l'analyse |
|---|---|---|
| Prix et graphiques | `packages/data`, historiques ajustés | valorisation, rendements, covariance, drawdown |
| FX | adaptateur de données à compléter | conversion des valeurs **et** des historiques |
| Fondamentaux | `packages/fundamentals` | expositions qualité/valorisation, jamais rendement certain |
| Résultats | `packages/events` | risque binaire et blackout documenté |
| Macro/régime | `packages/regime` | stress et contraintes conditionnelles datées |
| ML | `packages/ml` | estimateur facultatif daté, OOS, avec incertitude |
| Risque | `packages/portfolio`, `packages/risk` | métriques, budgets de risque, contraintes et veto |
| Explication | `packages/llm` via API uniquement | reformulation de résultats structurés, aucun calcul |

Les pages du site ne sont pas les sources de vérité : elles sont des vues. L'analyse doit appeler
les mêmes services/domaines que ces pages afin d'éviter des formules ou des dates divergentes.

## Pipeline cible

1. Résoudre chaque ligne par identifiant, place, devise et type de véhicule ; ne jamais joindre sur
   le ticker seul lorsqu'il est ambigu.
2. Créer un snapshot immuable lié à un utilisateur et à une version des positions.
3. Charger les prix ajustés et FX point-in-time, puis aligner les calendriers via le panel commun.
4. Construire un `evidence bundle` daté : prix, fondamentaux, événements, régime et sorties ML.
5. Calculer le diagnostic classique sans ML. Toute valeur indisponible reste `null` avec sa raison.
6. Construire des scénarios sous contraintes, sur la même fenêtre et avec les mêmes conventions.
7. Ajouter le ML uniquement comme variante comparée au benchmark classique ; jamais comme poids brut.
8. Générer l'explication française depuis les résultats structurés et leur lignage.

## Profils d'allocation

Les termes **prudent**, **neutre** et **dynamique** décrivent des objectifs relatifs à l'univers
autorisé, pas un niveau de sécurité absolu.

- **Prudent** : minimum variance robuste, plafonds d'exposition, liquidité minimale et turnover borné.
- **Neutre** : equal risk contribution/HRP, avec budgets de risque explicites.
- **Dynamique** : compromis rendement-risque seulement si les estimations OOS sont fraîches et
  suffisamment calibrées ; sinon statut `UNCALIBRATED` et scénario non publié.
- **Personnalisé** : contraintes déclarées par l'utilisateur, sans relaxation silencieuse.

Chaque résultat doit publier poids avant/après, turnover, spread, commissions, slippage, impact,
coûts non modélisés, métriques comparables et contraintes actives. Une impossibilité doit retourner
les contraintes incompatibles au lieu de fabriquer une solution.

## Garde-fous ML et données

- validation walk-forward ou purged/embargoed CV ; preprocessors ajustés sur le train seulement ;
- DSR/PSR et multiple testing enregistrés, comparaison champion/challenger ;
- horizon, date, version, univers d'entraînement et incertitude attachés à chaque estimation ;
- score de classification jamais utilisé directement comme rendement attendu ;
- repli automatique vers covariance/optimisation classique si le modèle est absent ou obsolète ;
- absence de forward-fill arbitraire entre calendriers crypto, actions et FX ;
- aucune donnée de démonstration présentée comme recommandation réelle.

## Frontière avec l'exécution

L'onglet reste analytique. Il n'importe ni `packages.execution` ni le portail de risque et ne peut
émettre aucun ordre. Une éventuelle action future « préparer un plan » devra créer un artefact
distinct, soumis explicitement à `scripts/run_live.py` et aux contrôles existants. Importer,
diagnostiquer ou simuler ne doit jamais déclencher ce passage.

## Ordre de livraison

1. **Fait** — import/confirmation/snapshot local et diagnostic croisé read-only.
2. **Partiel** — historiques réels, alias crypto, cash, alignement et diagnostic reproductible livrés
   en local ; restent la résolution persistée, l'isolation multi-utilisateur et le FX multi-devises.
3. **Livré pour prudent/neutre** — min-variance/ERC/HRP recalculés sur l'univers exact ; le plafond
   est appliqué par projection sur le simplex lorsqu'il est faisable. Compteur de déclenchements,
   effet moyen, turnover et coût linéaire sont publiés. Restent l'impact non linéaire et le dynamique,
   maintenu `UNCALIBRATED` tant qu'aucun rendement attendu OOS défendable n'existe.
3. **Partiel** — min-variance/ERC/HRP recalculés sur l'univers exact ; turnover, coût linéaire et veto
   de poids maximal publiés. Restent les contraintes complètes et l'impact non linéaire.
2. Résolution serveur et isolation utilisateur, puis historiques/FX réels et diagnostic reproductible.
3. **Partiel** — comparaison min-variance/ERC/Black-Litterman réutilisée uniquement si l'univers
   correspond exactement ; turnover, coût linéaire et veto de poids maximal sont publiés. Le
   recalcul dédié, les contraintes complètes et l'impact non linéaire restent à livrer.
4. Enrichissements fondamentaux/macro/événements, puis variante ML OOS et explication bornée.
5. OCR opt-in, stress historiques et Monte-Carlo reproductible.
