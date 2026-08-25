# Roadmap — Quant Terminal

> Mise à jour : 2026-08-25. Priorisation issue de l'audit (`docs/PROJECT_AUDIT.md`) et de deux
> exécutions réelles des labos de recherche.
> Règle de lecture : **P0 = à traiter avant tout paper trading sérieux.** Un P0 ouvert signifie
> que des chiffres publiés par le système ne sont pas fiables.

---

## P0 — Critique

### P0-1 · Migrer les 13 sites `min(len(data[s]))` restants
**Description.** Le motif `L = min(len(data[s]) for s in syms)` laisse la série la plus courte
fixer la profondeur de tout le panel. Corrigé le 25/08 dans `preset_backtest` et
`_price_universe` (7 → 126 rebalancements sur données réelles) ; le même motif subsiste dans
`conviction_backtest`, `megacap` (×2), `crypto_sleeve`, `sector_momentum`, `weighting_backtest`,
`ml_walkforward` et 4 fonctions de `preset_backtest`.
**Difficulté.** Faible par site, moyenne au total (chaque site a ses invariants de test).
**Dépendances.** `packages/backtest/panel.fenetre_commune` — déjà écrit et testé.
**Risques.** Les chiffres publiés vont changer, parfois beaucoup. C'est le but : les chiffres
actuels sont faux. Prévoir de republier les résultats du vault.

### P0-2 · Rendre mesurable le biais du survivant
**Description.** 7 délistés sont ingérés, aucun n'entre jamais dans le top-30 : le test s'exécute
et ne mesure rien. Il faut ingérer des délistés qui **auraient été sélectionnés** — c'est-à-dire
bien classés avant leur disparition.
**Difficulté.** Moyenne — l'obstacle est la donnée, pas le code.
**Dépendances.** `packages/data/survivorship`, source de délistés historiques avec prix.
**Risques.** Le résultat sera probablement défavorable. C'est une information, pas un échec.

### P0-3 · Instruire la bande d'inaction
**Description.** La bande de 3 % en poids absolu bloque 99 % des pas et ne laisse trader que ~7 %
des noms. À 30 lignes, une position pèse ~3,3 % : la bande vaut presque une position entière.
Mesurer une bande **relative** au poids cible avant de conclure.
**Difficulté.** Faible (une config de labo).
**Dépendances.** `scripts/preset_lab.py`.
**Risques.** Une bande plus fine augmente le turnover, donc les coûts. Le labo doit trancher, pas
l'intuition.

---

## P1 — Important

### P1-1 · Brancher ou supprimer `RiskEngine`
**Description.** `packages/risk/engine.py` (reward/risk, stops, max positions) n'est instancié
que dans `scripts/demo_*.py`. `order_gate` couvre désormais le chemin de production, mais les
règles de stop et de reward/risk restent hors circuit. Décider : les brancher, ou les déclarer
explicitement réservées au moteur de streaming.
**Difficulté.** Moyenne. **Dépendances.** `scripts/run_live.py`, `order_gate`.
**Risques.** Doubler les couches sans clarifier les responsabilités produirait deux vérités.

### P1-2 · Couvrir `mcp_tradingview`
**Description.** 7 modules, 2 fichiers de test, et il pilote un kill-switch qui peut ramener
l'exposition à zéro. Un faux positif coupe tout le portefeuille ; un faux négatif désarme la
protection.
**Difficulté.** Faible. **Risques.** Aucun à écrire des tests ; élevé à ne pas le faire.

### P1-3 · Alimenter `Source.exactitude_passee`
**Description.** Le champ existe dans `packages/intelligence/sources.py`, contribue jusqu'à ±0,20
au score, et n'est alimenté par rien. C'est le facteur le plus discriminant du scoring et il est
vide.
**Difficulté.** Moyenne (exige de stocker les verdicts et de les confronter aux faits ensuite).
**Dépendances.** Collecteurs + persistance (voir P1-4).

### P1-4 · Collecteurs pour la couche d'intelligence
**Description.** `packages/intelligence` est une architecture testée **sans collecteur** : ni X,
ni RSS, ni sources officielles, ni persistance. Premier livrable attendu de Grok Bot.
**Difficulté.** Moyenne à élevée (accès API X, quotas, coûts).
**Dépendances.** Aucune côté code — tout le contrat est déjà défini et testé.
**Risques.** Un collecteur qui contourne `qualifier()` réintroduirait le problème que toute la
couche existe pour empêcher.

### P1-5 · Authentifier la watchlist X
**Description.** 66 comptes, zéro authentifié, un handle non résoluble (`"Jensen Huang"` est un
nom). Chaque compte doit être vérifié individuellement avant tout usage.
**Difficulté.** Faible mais fastidieuse. **Risques.** Marquer `verifie=True` sans vérification
réelle détruirait la valeur du scoring.

### P1-6 · Séries macro additionnelles
**Description.** NFCI, point mort d'inflation 5a5a, indice dollar, ICSA, spread IG. Les
identifiants FRED doivent être vérifiés sur la machine de l'utilisateur.
**Difficulté.** Faible. **Dépendances.** `packages/macro/fred.py` (détection de péremption déjà
en place).

---

## P2 — Optimisation

### P2-1 · Exécuter `impact.py` et `almgren_chriss.py` sur données réelles
Écrits et testés, jamais exécutés hors des tests. Tant qu'ils n'ont pas tourné, ils ne sont pas
validés — `impact.py` porte d'ailleurs un défaut de calibration explicitement documenté.

### P2-2 · Mesurer la couverture de tests
`pip install pytest-cov`, puis publier le chiffre. Aujourd'hui **non mesurée**.

### P2-3 · CCXT pour l'exécution crypto
API unifiée sur 100+ places, en miroir d'`AlpacaBroker`. Paper par défaut, sans exception.

### P2-4 · Moteur vectorisé pour les sweeps
`vectorbt` ou `qlib` pour la recherche massive ; garder `fast_swing` pour le snapshot.
L'adaptateur `packages/backtest/vectorbt_adapter.py` existe déjà.

### P2-5 · Fondamentaux point-in-time
Aujourd'hui le score du jour est appliqué à des dates passées en production. L'univers de
backtest est sélectionné par momentum prix-only pour l'éviter, mais la donnée reste non
historisée.

---

## P3 — Expérimental

### P3-1 · Décision sur le débruitage RMT
`k_signal` médian = 1 sur 126 rebalancements : l'ERC répartit du risque sur une matrice à une
seule direction fiable. Le repli inverse-vol donne un CAGR supérieur mais un Sharpe et un maxDD
inférieurs. Aucune des deux options ne gagne clairement — à réexaminer sur une période disjointe.

### P3-2 · Nouvelles classes d'actifs
Forex, dérivés. Exige des données, un modèle de coûts et un modèle de risque distincts. Ne pas
lancer avant les P0.

### P3-3 · Bot Discord
Question réglementaire ouverte : diffuser des signaux à des tiers relève potentiellement du
conseil en investissement. À trancher avec un avis juridique, pas techniquement.

### P3-4 · Découper `apps/web/app/dashboard/page.tsx`
435 lignes pour une limite projet à 400. Deux composants ont déjà été extraits (509 → 435).
