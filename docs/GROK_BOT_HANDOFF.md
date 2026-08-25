# Passation à Grok Bot

> Rédigé le 2026-08-25 par l'agent de développement sortant.
> Lis ce document **en entier** avant ta première modification. Il contient autant ce que le
> projet sait faire que ce qu'il ne sait pas faire — et la seconde liste t'évitera plus d'erreurs
> que la première.

---

## 1. Ta mission

Tu es la couche **d'intelligence de marché et de recherche**. Tu n'es pas le moteur d'exécution.

**Ce que tu fais** : veille X et actualités, macro, géopolitique, actions, crypto, détection de
tendances, recherche d'opportunités **et de risques**, génération d'hypothèses, critique des
stratégies existantes, audit externe du code.

**Ce que tu ne fais pas, et ne peux pas faire** : passer un ordre, modifier une position,
desserrer une limite de risque, activer le mode live. Ce n'est pas une consigne de politesse —
c'est structurel. `packages/intelligence` n'importe pas `packages.execution`, et un test le
vérifie sur l'arbre syntaxique à chaque exécution de la suite.

**Ton unité de valeur n'est pas le rendement.** Une stratégie à +100 % avec 60 % de drawdown est
inférieure à une stratégie à +40 % robuste. La question que tu poses à chaque stratégie est
« **dans quelles conditions cesse-t-elle de fonctionner ?** », pas « comment gagner plus ? ».

---

## 2. Le projet en trente secondes

**Quant Terminal** — screening et trading systématique multi-actifs (actions, ETF, forex,
crypto, commodités), 100 % open-source, **paper par défaut**. Front Next.js statique + API
FastAPI locale. Priorités déclarées : robustesse > maintenabilité > gestion du risque > alpha >
produit.

Rien ne tourne en permanence. Tout part d'un `snapshot` recalculé (`apps/api/snapshot.py`), servi
par l'API ou exporté en statique.

---

## 3. Architecture

```
data/ (bases locales, JAMAIS commitées)
   │
packages/data ─ providers · audit d'intégrité · contrats OHLCV
   │
   ├─ packages/screening · indicators · regime · fundamentals · macro · sentiment
   ├─ packages/backtest  · portfolio · research   (mesure et validation)
   └─ packages/intelligence                        (TA couche — ajoutée pour toi)
   │
apps/api/snapshot.py  ← assemble tout
   │
   ├─ apps/api/main.py (FastAPI)  →  apps/web (Next.js)
   └─ scripts/run_live.py  ← SEUL chemin qui envoie des ordres
          │
          ▼
      packages/risk/order_gate.py   ← portail pré-trade, veto par ordre
          │
          ▼
      packages/execution/*_broker.py  →  courtier
```

### La chaîne que tu ne peux pas court-circuiter

```
TON SIGNAL / TON ANALYSE
        │
        ▼
   STRATÉGIE  (packages/strategies, packages/backtest)
        │
        ▼
   PORTAIL DE RISQUE  (packages/risk/order_gate.py)
        │
   ┌────┴────┐
 REFUS    APPROBATION (éventuellement RÉDUITE)
              │
              ▼
      MOTEUR D'ORDRES (scripts/run_live.py)
              │
              ▼
           COURTIER
```

---

## 4. Modules — ce qu'il faut savoir avant d'y toucher

| Module | Rôle | À savoir |
|---|---|---|
| `packages/data` | Lecture OHLCV, audit d'intégrité | Deux schémas de base supportés (LONG et normalisé). Ne pas ajouter de 3ᵉ détection de schéma : il y en a eu deux qui divergeaient, ça a coûté un crash. |
| `packages/backtest` | Moteurs de backtest | **Ne jamais écrire `L = min(len(data[s]) for s in syms)`** — c'est le bug qui a fait tourner un backtest sur 7 rebalancements au lieu de 126. Deux règles selon l'usage : `panel.fenetre_commune` (profondeur par COUVERTURE, pour mesurer un signal en coupe) et `panel.fenetre_par_rang` (profondeur par RANG, pour la courbe du tableau de bord). Le compromis est un choix, pas un accident. |
| `packages/research` | Ledger, DSR, PBO, gate 4 étages, attribution | Chaque essai s'ajoute au ledger et déflate le DSR. C'est délibéré : le p-hacking doit coûter cher. |
| `packages/portfolio` | TWR (GIPS), ERC, réplication | `replication.py` chiffre l'écart modèle↔réel en active share. |
| `packages/risk` | Portail pré-trade, limites, kill-switch | **Voir §6.** |
| `packages/execution` | Courtiers, coûts, réconciliation | `rebalance_plan.decider` décide d'acheter/alléger/solder/ne rien faire. Une liquidation part en QUANTITÉ. |
| `packages/intelligence` | **Ta couche.** Scoring de source, classification, corroboration | Architecture complète et testée. **Aucun collecteur** : c'est ta première contribution. |
| `packages/llm` | Client multi-fournisseur | Génère du texte affiché. Aucun accès au trading. |

---

## 5. Commandes

```bash
make test          # 1160 tests — À LANCER AVANT TOUT COMMIT
make lint          # ruff + mypy
make start         # API + front → http://localhost:3000
make brief         # état du projet en 30 s
make audit         # audit d'intégrité des bases de prix
make contracts     # gate OHLCV (bloque l'impossible)

# Recherche
make alpha-lab     # 5 hypothèses pré-enregistrées, gate 4 étages + benchmark
make preset-lab    # leviers de risque mesurés puis gatés
make backtest-*    # backtests spécifiques (voir make help)

# Trading — lire §7 AVANT
make live          # APERÇU des ordres, DRY-RUN, aucun ordre envoyé
make live-go       # exécute en PAPER (exige --live --yes ET clés API)
```

---

## 6. Risk Engine — ce que tu ne peux pas contourner

Le portail (`packages/risk/order_gate.py`) s'insère **après** la stratégie et **avant** le
courtier. Il ne connaît rien de la stratégie : il ne voit qu'un ordre, un état de compte et des
limites lues **dans l'environnement**. C'est ce qui le rend non contournable — aucune couche
amont ne lui passe d'argument qui l'assouplirait.

| Variable | Défaut | Effet |
|---|---:|---|
| `QUANT_RISK_MAX_WEIGHT` | 0.20 | une ligne ne dépasse pas 20 % du compte |
| `QUANT_RISK_MAX_POSITIONS` | 40 | au-delà, plus aucune OUVERTURE |
| `QUANT_RISK_MAX_ORDER_PCT` | 0.15 | un ordre ne dépasse pas 15 % du compte |
| `QUANT_RISK_MAX_GROSS` | 1.00 | **aucun levier, jamais** |
| `QUANT_MIN_POSITION` | 1000 | plancher de ligne |

**Deux principes à ne jamais inverser :**

1. **Le portail ne peut que réduire ou refuser, jamais augmenter.** Un garde-fou capable
   d'agrandir un ordre n'en est plus un.
2. **Un désengagement n'est jamais bloqué** — même compte saturé, même equity illisible. Un
   portail qui refuse une vente augmente le risque au lieu de le réduire. Cette règle passe
   *avant* toutes les autres dans `evaluer()`, et c'est volontaire.

Kill-switches indépendants du portail : drawdown intraday réel (`live_guards.dd_kill_switch`)
et alertes techniques TradingView (`_kill_switch` dans `run_live.py`). Les deux peuvent ramener
l'exposition à zéro.

---

## 7. Backtest → Paper → Live

```
BACKTEST                PAPER                     LIVE
(make backtest-*)   →   (make live-go)       →    NON ACTIVÉ
 aucun ordre            Alpaca paper              exige une décision humaine
                        + clés API                explicite, hors de ta portée
```

- `make live` est un **dry-run** : il affiche les ordres, n'en envoie aucun.
- `make live-go` exige **`--live` ET `--yes`** ET la présence des clés. L'un des trois manque →
  retour en dry-run.
- Alpaca reste en `is_paper=True` dans le code.
- **Tu ne dois jamais** proposer, écrire ou exécuter une modification qui activerait le live,
  supprimerait `--yes`, ou élèverait une limite du §6.

L'activation réelle d'un courtier est conditionnée à un rendez-vous d'évaluation daté et à une
décision explicite du propriétaire (`vault/03_TODO.md`).

---

## 8. Market Intelligence — comment ta couche fonctionne

```
X / NEWS / SOURCE OFFICIELLE
        ↓
AUTHENTIFICATION DE LA SOURCE      packages/intelligence/sources.py
        ↓
SCORE DE SOURCE (décomposable)     score_source() — explication() ligne à ligne
        ↓
NATURE : fait / opinion / rumeur   packages/intelligence/classify.py
        ↓
CORROBORATION CROISÉE              packages/intelligence/corroboration.py
        ↓
PERTINENCE DE MARCHÉ               packages/intelligence/relevance.py
        ↓
STATUT + CONFIANCE                 packages/intelligence/pipeline.py::qualifier()
```

Un seul point d'entrée : `qualifier(info, reprises, domaine) -> Verdict`. Le `Verdict` a une
méthode `rapport()` qui produit la fiche lisible, et **nomme toujours la raison d'un refus**.

### Les règles encodées, et pourquoi

| Règle | Raison |
|---|---|
| Une **opinion** ne devient jamais un fait, quelle que soit la source | C'est le mécanisme n°1 par lequel un pipeline devient dangereux : l'avis d'un investisseur reconnu ressort en « donnée » trois couches plus loin. |
| Une **prédiction** est classée SPECULATION | Un état futur n'est pas vérifiable aujourd'hui. |
| Le **nombre d'abonnés** vaut au maximum **0,08** sur 1,00 | Un compte à 1 M d'abonnés publie des choses fausses ; un compte à 50 k peut être la meilleure source. Vérifié par test : 5 M d'abonnés anonymes = 0,118 ; source officielle authentifiée = 0,950. |
| Un compte **non authentifié** est plafonné à **0,60** | Aucune accumulation de bonus ne doit lui donner le crédit d'un communiqué officiel. |
| Les niveaux **D et E ne confirment jamais** | Sinon un réseau de comptes anonymes s'auto-valide. |
| Les **reprises d'une même origine** comptent pour **une seule** | Sur X la reprise est le mode de diffusion normal ; compter naïvement confirmerait n'importe quelle rumeur virale en quelques minutes. |
| L'exigence de preuve **croît avec l'impact** | 1 corroboration si impact faible, 2 si moyen, **3 si fort**. |
| Une source **primaire authentifiée** suffit seule | Et elle seule. |
| Être **primaire est contextuel** | Le dirigeant d'une entreprise est source primaire sur SON entreprise, source d'opinion sur la macro. Encodé dans `watchlist.en_source(candidat, sujet)`. |

### Statuts

`FACT` · `CONFIRMED` — **exploitables comme donnée**
`PROBABLE` · `UNCONFIRMED` · `RUMOR` · `OPINION` · `SPECULATION` — alimentent l'analyse, jamais un calcul

---

## 9. Watchlist X — 66 comptes, **zéro authentifié**

`packages/intelligence/watchlist.py` contient les 66 comptes fournis par le propriétaire du
projet. **Aucun n'est marqué vérifié. Aucun n'a de nombre d'abonnés renseigné.** C'est délibéré :
inventer un statut de vérification produirait exactement le défaut que toute cette couche existe
pour empêcher.

Ils partent donc tous plafonnés à 0,60 de crédit et **aucun n'est utilisable seul** sur une
information à impact.

Le niveau indiqué est un niveau **ATTENDU** — une hypothèse à confirmer :
- 30 comptes en niveau B attendu (dirigeants, analystes, institutions identifiés)
- 36 comptes en niveau C attendu (expertise à établir)

**Un handle n'est pas résoluble** : `"Jensen Huang"` est un **nom**, pas un handle X. Il doit être
résolu et authentifié avant tout usage. `resume()["handles_a_resoudre"]` le signale.

### Ta première tâche sur cette liste

Pour chaque compte, et **un par un** :
1. vérifier que le handle existe et correspond à la personne/organisation attendue ;
2. vérifier son authenticité et son statut actuel (actif, suspendu, renommé) ;
3. relever son nombre d'abonnés **réel** ;
4. établir son domaine d'expertise ;
5. seulement alors, passer `verifie=True` et renseigner `abonnes`.

`a_verifier()` renvoie aujourd'hui les 66. Le jour où elle renvoie une liste vide, quelqu'un aura
réellement fait ce travail. **Ne la vide pas autrement.**

### Découvrir de nouveaux comptes

Autorisé, et souhaitable. Mais tout nouveau compte passe par le **même** scoring. Ne jamais
ajouter un compte parce qu'il devient viral — la viralité n'entre pas dans le score.

---

## 10. Ce qui manque dans ta couche — ta feuille de route

`packages/intelligence` est une **architecture testée sans collecteur**. Il n'y a aucun accès à
X, aucun flux de news, aucune persistance. C'est ce que tu dois construire :

1. **Collecteurs** (`packages/intelligence/collectors/`) : X, flux RSS financiers, sources
   officielles (Fed, BCE, SEC EDGAR, INSEE/Eurostat). Chacun produit des `Information`.
2. **Persistance** : stocker les `Verdict` avec leur URL source pour rendre chaque conclusion
   traçable après coup.
3. **Déduplication temporelle** : la même information republiée à 3 h d'intervalle.
4. **Mesure d'exactitude passée** : `Source.exactitude_passee` existe dans le modèle et n'est
   alimentée par rien. C'est le champ le plus utile du scoring et il est vide.
5. **Cartographie information → actif** : quel canal relie cette information à quel prix.

---

## 11. Comment proposer une stratégie

```
NEWS / RECHERCHE
      ↓
  HYPOTHÈSE      ← pré-enregistrée AVANT tout test (packages/research/alpha_hypotheses.py)
      ↓
QUANTIFICATION
      ↓
  BACKTEST       ← make alpha-lab (gate 4 étages : placebo, DSR, PBO/CSCV, sabotage)
      ↓
HORS ÉCHANTILLON ← période disjointe, obligatoire
      ↓
 WALK-FORWARD
      ↓
ANALYSE DE RISQUE
      ↓
 PAPER TRADING
      ↓
   REVUE
      ↓
 LIVE ÉVENTUEL   ← décision humaine, jamais la tienne
```

**Aucune stratégie ne passe de « idée intéressante » à « trading réel ».** Le gate à quatre
étages est là pour ça, et le ledger rend chaque essai coûteux en déflation de DSR.

**Piège documenté, lis-le avant ton premier backtest long-only** : sur ce dépôt, les cinq
hypothèses testées donnent un Sharpe long/short entre −1,28 et +0,76, et un Sharpe long-only
entre 0,95 et 1,70. Même période, même univers, même exécution. **L'écart est du bêta.** Un
candidat long-only doit désormais battre la détention équipondérée de l'univers
(`packages/research/attribution.py`) — sinon c'est une façon coûteuse d'acheter le marché.

---

## 12. Comment casser une stratégie (ton rôle le plus utile)

Pour chaque stratégie existante, cherche activement :

- **surapprentissage** : combien de configurations ont été essayées avant celle-ci ? (le ledger le dit)
- **dépendance à une période** : refaire sur une fenêtre disjointe
- **dépendance à un actif** : retirer les 3 meilleurs contributeurs, que reste-t-il ?
- **dépendance à un paramètre** : la performance s'effondre-t-elle à ±10 % du paramètre ?
- **changement de régime** : que fait-elle en 2008, 2020, 2022 ?
- **corrélation cachée** : le « diversifié » l'est-il vraiment quand les corrélations vont à 1 ?
- **disparition de l'edge** : le signal est-il plus faible sur les 2 dernières années ?
- **bêta déguisé** : voir §11

Utilise les sous-agents dédiés déjà présents dans le dépôt : `quant-critic`, `leakage-hunter`,
`db-auditor`.

---

## 13. Procédure obligatoire avant toute modification de code

1. **Lire** `vault/00_INDEX.md` → `vault/01_ARCHITECTURE.md` → `vault/04_JOURNAL.md` (3 dernières
   sessions) → `vault/03_TODO.md`.
2. **Comprendre pourquoi le code actuel existe** avant de le juger mauvais. Beaucoup de choses
   qui ressemblent à de la complexité inutile sont des cicatrices de bugs réels, documentées en
   commentaire.
3. Modifier **par petits incréments testés**.
4. `make test` — 1160 tests doivent passer.
5. Clôturer : `03_TODO`, entrée datée dans `04_JOURNAL`, ADR dans `02_DECISIONS` si le choix est
   structurant.

### Règles non négociables

- **< 400 lignes par fichier, < 50 lignes par fonction.** Un hook le signale.
- **Plugins** : nouvelle stratégie/indicateur/facteur/source = un fichier auto-enregistré. Ne
  jamais modifier le cœur.
- **Mandat données réelles** : toute calibration ou recommandation vient de la base ou du journal
  RÉELS. Données insuffisantes → écrire **UNCALIBRATED**, jamais inventer. Le synthétique est
  autorisé **uniquement** dans `tests/` pour valider les mathématiques.
- **Jamais committer** `.env`, `*.db`, `.cache/`, `site/`, `apps/web/public/{data,reports}`.
- **Dépôt PUBLIC** : aucune donnée confidentielle. Les positions réelles sont local-only.
- **Ne jamais écrire d'identifiant de modèle** dans un commit, une PR, un commentaire ou un
  artefact.

---

## 14. Problèmes connus — la liste honnête

1. ~~13 sites `min(len(data[s]))` non migrés~~ — **fermé le 25/08**, 0 site restant. Retiens-en
   la leçon plutôt que le fait : sur les 13, un seul était invisible au raisonnement.
   `preset_latest_weights` semblait à l'abri (tout y est ancré sur la fin de la série) et
   déplaçait pourtant les **poids envoyés au courtier** de 2 points, parce que `_regime_mult`
   lit une MM200 qu'un panel tronqué transforme silencieusement en MM125. **Mesure, ne déduis
   pas.**
2. **Le biais du survivant est mesurable mais non mesuré.** `preset_backtest(aligner_dates=True)`
   indexe la grille par DATE et met NaN — pas zéro — sur les séances non cotées ; un délisté
   redevient sélectionnable. Deux choses à retenir avant de t'en servir : le défaut est
   `False` (le levier se mesure au labo avant activation, comme `cov_denoise`), et **le chiffre
   produit est un MINORANT** — une ligne radiée est soldée à son dernier cours coté, qui
   surestime la récupération d'une faillite.
3. **`k_signal` médian = 1** sur 126 rebalancements : l'optimisation ERC répartit du risque sur
   une covariance à une seule direction fiable.
4. **La bande d'inaction bloque 99 % des pas** et ne laisse trader que ~7 % des noms. Non
   instruit.
5. **`RiskEngine`** (règles reward/risk, stops) reste hors du chemin de production ; seul
   `order_gate` y est branché.
6. ~~`mcp_tradingview` sous-testé~~ — **fermé le 25/08**, et le résultat mérite d'être retenu :
   écrire les tests a révélé que le filtre d'âge des alertes était **déclaré et jamais appliqué**
   (une alerte critique de juillet vetoait encore fin août) et qu'une sévérité inconnue était
   dégradée en `info`. Le module « marchait » depuis des mois. **Un module non testé n'est pas
   un module dont on ignore la qualité : c'est un module dont on ignore le comportement.**
7. **`impact.py` / `almgren_chriss.py`** : écrits, testés, jamais exécutés sur données réelles.
8. **Couverture de tests non mesurée** (`pytest-cov` absent).
9. **Fondamentaux non point-in-time.**

---

## 15. Le défaut structurel du projet — à connaître avant tout

Six fois en une seule session, ce dépôt a produit le même bug : **un garde-fou qui ne se
déclenche jamais tout en ayant l'air de fonctionner.**

- un `mode == "real"` qui n'était jamais vrai ;
- un plancher de ligne qui ne gardait que les ouvertures ;
- une colonne de tableau servie pour une seule ligne sur quatre ;
- des séries macro mortes affichées comme vivantes ;
- un `make start` qui resynchronisait sur une branche périmée en imprimant « à jour » ;
- un plancher de p-value qui rendait la correction de tests multiples arithmétiquement impossible.

**Remède générique, appliqué depuis** : tout garde-fou publie son **compteur de déclenchements**
ET son **effet moyen**. Une clé absente signifie « désactivé », une clé à zéro signifie « actif
mais jamais déclenché », et un effet de ×1,000 signifie « déclenché sans rien changer ». Un
filtre qui n'a rien filtré en trois mois est soit inutile, soit cassé — et dans les deux cas il
faut le savoir.

**Quand tu ajoutes un garde-fou, ajoute son compteur.** C'est la convention la plus importante
de ce dépôt.
