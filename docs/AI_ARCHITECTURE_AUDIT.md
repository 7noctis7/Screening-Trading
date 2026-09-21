# Audit d'architecture Quant AI — PHASE 1

> Cartographie du dépôt avant toute ligne de code, conformément au point 70 du brief.
> Date : 2026-09-16 · Commit : voir `git log`.

---

## 0. La mesure qui doit précéder toute décision

L'artefact ML **actuellement en production** porte ses propres métriques :

```
models/ml_7cbe18791f60247c.pkl
  auc   = 0.504      ← une pièce de monnaie fait 0.500
  brier = 0.2496     ← le plancher de `promotion.py` est 0.25
  dsr   = None       ← jamais calculé
```

**Le modèle n'a aucun pouvoir discriminant mesurable.** AUC 0,504 sur un problème binaire
est statistiquement indiscernable du hasard, et le Brier est à 0,0004 du seuil de rejet.

Cela ne condamne pas le projet — cela **ordonne** la mission. Le brief demande une
infrastructure GPU pour entraîner plus vite. Or :

| | |
|---|---|
| Modèle en production | régression logistique numpy / XGBoost sur features tabulaires |
| Besoin GPU réel | **aucun** — ces modèles s'entraînent en secondes sur CPU |
| Ce qu'un GPU accélérerait | transformers (FinBERT), grands balayages HPO, réseaux profonds |
| Edge actuel à accélérer | **AUC 0,504** |

Louer un GPU pour entraîner plus vite un modèle sans edge, c'est payer pour atteindre
le hasard plus rapidement. Le brief le dit lui-même (point 73) : *COÛT-AJUSTÉ > PERFORMANCE
BRUTE*, *MESURE > INTUITION*.

**Conséquence sur l'ordre proposé** : construire d'abord ce qui permet de SAVOIR si un
modèle vaut quelque chose (registry, manifest, traçabilité), puis ce qui produit de
l'information nouvelle (NLP structuré), et seulement ensuite le compute distant.

---

## 1. Cartographie — ce qui existe déjà

### 1.1 Volumétrie

| Paquet | Fichiers | Lignes | Rôle |
|---|---:|---:|---|
| `research` | 47 | 5 840 | bancs de mesure, excursions, coûts d'exécution |
| `portfolio` | 55 | 5 261 | métriques, allocation, fragilité |
| `backtest` | 33 | 4 365 | moteurs, banc swing, price action |
| `data` | 36 | 3 683 | providers, audit, index history |
| `execution` | 31 | 3 635 | courtiers, journal, calendrier, garde journalière |
| `ml` | 20 | 1 650 | **le cœur ML — voir 1.2** |
| `sentiment` | 10 | 832 | FinBERT, lexique, RSS, PIT, risk gate |
| `llm` | 5 | 663 | Ollama local, client OpenAI-compatible, garde |
| `intelligence` | 7 | 652 | classification, corroboration, pertinence |

Tests : **2 779 passés, 75 ignorés** (43 fichiers en `execution`, 50 en `research`, 22 en `ml`).

### 1.2 `packages/ml` — inventaire réel

| Module | Ce qu'il fait | Couvre le point |
|---|---|---|
| `cv.py` | PurgedKFold + embargo (AFML ch. 7) | 13, 14 |
| `cpcv.py` | CV combinatoire purgée → dispersion des chemins | 14, 36 |
| `uniqueness.py` | poids d'unicité des labels chevauchants (ch. 4) | 13 |
| `labeling.py` | triple-barrière + meta-labeling (ch. 3) | 14 |
| `meta.py` | méta-modèle « agir ou non » | 29 |
| `features.py` | différenciation fractionnaire + assemblage PIT | 12, 13 |
| `model.py` | interface commune, Logit numpy, sklearn, XGBoost | 14 |
| `calibration.py` | Brier, courbe de fiabilité | **30** |
| `conformal.py` | prédiction conforme (couverture garantie) | 30 |
| `drift.py` | PSI — dérive de distribution | **47** |
| `hpo.py` | Optuna, repli recherche aléatoire | **35** |
| `promotion.py` | gate DSR/Brier champion vs challenger | **37, 48** |
| `governance.py` | champion/challenger + registre **en mémoire** | 9 (partiel) |
| `tracking.py` | MLflow optionnel, non bloquant | 33 (partiel) |
| `artifact.py` | cache TTL 24 h + sidecar SHA-256 | 8, 11 (partiel) |
| `sizing.py` | taille pilotée par la confiance (bet sizing) | 15 |
| `evaluation.py` | métriques + score en CV purgée | 14 |
| `explication.py` | pourquoi le modèle a dit ça | 60 |

### 1.3 Profit capture, MFE/MAE, sorties — **déjà construits**

Les points 17, 18 et 19 du brief décrivent un travail qui existe :

- `packages/reporting/mfe_mae.py` — analyse MFE/MAE du journal → corrections SL/TP
- `packages/research/excursions.py` — comble les MFE/MAE manquantes des fermetures reconstruites
- `scripts/sortie_lab.py` — banc de sorties : balayage (cible × suiveur), avec l'avertissement
  méthodologique que MFE/MAE seules **ne permettent pas** de reconstruire « et si j'avais pris
  à 3R ? » (on ignore l'ORDRE des excursions) — seul un rejeu de backtest le peut
- `packages/portfolio/pv_latente.py`, `scripts/diag_pv_latente.py` — plus-value latente
- `make labs` — cinq bancs : candidats, sorties, dimensionnement, signaux, régime ATR

### 1.4 IA locale — ce qui existe

`packages/llm/local.py` parle **déjà** à Ollama (`/api/tags`, `/api/chat`, `OLLAMA_HOST`,
`QUANT_LOCAL_LLM`), en stdlib pure, avec routage « local gratuit d'abord, repli serveur
OpenAI-compatible, sinon rien ».

**Ce qu'il ne fait pas** : sortie structurée, Pydantic, timeout explicite, circuit breaker,
cache borné, concurrence bornée, métriques de fallback.

### 1.5 API — les routes IA existent déjà

```
/api/ai/status       disponibilité fournisseur + modèle, avec motif
/api/ai/diagnostic
/api/ai/commentary
/api/ai/metrics      fréquence de rejet du garde IA
/api/ml
```

Le brief (point 57) demande de les inspecter avant d'en créer : **il n'y a rien à créer**,
seulement à enrichir (point 58 : latence, fallback rate, circuit state, mémoire, versions).

### 1.6 Matériel

`packages/common/device.py` anticipe déjà Mac (MPS) → NVIDIA (CUDA), sans import lourd au
niveau module, avec `activer_cudf()` et une bannière. La couche d'abstraction matérielle
demandée existe en germe.

---

## 2. Les quatre trous réels

Tout le reste du brief est soit déjà construit, soit une extension de l'existant. Ce qui
manque VRAIMENT :

### A. Registry persistant et manifest de traçabilité *(points 7-9, 12, 33, 49, 51, 52, 68)*

`governance.ModelRegistry` est **en mémoire** : il meurt avec le processus. `artifact.py` est
un **cache TTL** indexé par hash de signature — pas un registre. Aucun modèle ne porte :

```
version · dataset_hash · feature_version · git_commit · training_run_id
prompt_version · seed · statut (candidate|production|archived|rejected)
```

Conséquence concrète, vérifiable : le `.pkl` en production ne permet pas de dire avec quelles
données ni depuis quel commit il a été produit. **Le rollback (point 68) est impossible.**

### B. NLP structuré et résilient *(points 23-28, 32)*

Manquent : schéma Pydantic `MarketSignalNLP`, `format=model_json_schema()`, `asyncio.wait_for`,
fallback NEUTRAL, circuit breaker CLOSED/OPEN/HALF_OPEN, cache borné, concurrence bornée,
versionnage de prompt.

### C. Abstraction compute + artifact store *(points 39-45, 43, 44)*

**Rien n'existe.** Ni `ComputeBackend`, ni `ArtifactStore`, ni cycle de vie de job, ni
auto-shutdown, ni suivi de coût.

### D. Verrou d'environnement *(points 53, 54)*

`pyproject.toml` déclare des extras sans versions épinglées (`xgboost`, `mlflow`, `optuna`…).
Pas de lockfile, pas de `Dockerfile.training`. Un entraînement distant ne serait pas
reproductible localement.

---

## 3. Architecture cible (PHASE 2)

### 3.1 Interfaces à créer — indépendantes du fournisseur

```
packages/mlops/
    registre.py        ModelRegistry persistant (JSON + artefacts versionnés)
    manifest.py        Manifest de run : dataset_hash, git_commit, seed, env, coût
    empreinte.py       SHA-256 d'un dataset / d'un artefact (réutilise safe_pickle)
    artefacts.py       ArtifactStore : local | ssh/rsync | s3/minio
    compute.py         ComputeBackend : submit_job / get_status / fetch / terminate
    backends/
        local.py       LocalBackend  (Mac, VPS)
        lambda_ai.py   LambdaBackend (GPU temporaire, auto-shutdown)
```

Règle d'or : `packages/mlops` **ne peut pas importer** `packages.execution` — vérifié par test
(points 64, 65). Un entraînement ne doit avoir aucun chemin vers un ordre.

### 3.2 Le cycle Lambda, avec DEUX protections

```
CREATE → BOOTSTRAP → DATA → TRAIN → VALIDATE → ARTIFACTS
   → CHECKSUM → UPLOAD → VERIFY → MARKER → TERMINATE
```

| Protection | Où elle vit | Ce qu'elle couvre |
|---|---|---|
| 1 — applicative | le script de job | fin normale, échec, exception |
| 2 — infrastructure | `MAX_RUNTIME` posé sur l'instance | le script lui-même est mort |

La seconde est la seule qui compte si la première plante. Elle doit être posée **à la création
de l'instance**, jamais par le job.

### 3.3 Promotion — le chemin complet

```
Lambda/local → artefact + manifest → checksum → téléchargement Mac/VPS
    → vérification checksum → validation de schéma → backtest → walk-forward
    → gates statistiques (placebo, DSR, PBO, sabotage) → CANDIDATE
        → décision HUMAINE → PRODUCTION
```

`promotion.should_promote` fournit déjà la dernière barrière. Ce qui manque est **avant** :
la traçabilité qui rend la décision auditable.

---

## 4. Ordre d'implémentation proposé

Différent du brief, et voici pourquoi : chaque étape doit rendre la suivante MESURABLE.

| # | Phase | Pourquoi ici | Sans GPU ? |
|---|---|---|---|
| 1 | **Registry + manifest + checksum** | sans traçabilité, aucun entraînement ne vaut la peine d'être lancé — on ne pourra pas dire ce qu'il a produit | oui |
| 2 | **Environment lock** | un run non reproductible n'est pas une mesure | oui |
| 3 | **NLP structuré** (Pydantic, timeout, circuit breaker) | produit de l'INFORMATION nouvelle ; c'est la seule voie plausible vers un edge que le tabulaire n'a pas donné | oui |
| 4 | **Mesure de l'alpha incrémental du NLP** | quant seul vs quant+NLP, hors échantillon. Si zéro → poids 0, et on s'arrête là | oui |
| 5 | **ComputeBackend + ArtifactStore + LocalBackend** | l'abstraction, éprouvée en local d'abord | oui |
| 6 | **LambdaBackend + auto-shutdown** | uniquement quand une charge le justifie vraiment | non |
| 7 | UI, observabilité, documentation | | oui |

Les étapes 1 à 5 se font **sur le Mac et le VPS, à coût nul**. L'étape 6 n'a de sens qu'après
que 4 ait démontré quelque chose.

---

## 5. Ce que l'audit recommande de NE PAS faire

- **Ne pas reconstruire** MFE/MAE, profit capture, bancs de sortie, CV purgée, drift PSI,
  HPO, calibration, gate de promotion : tout existe et est testé.
- **Ne pas créer** de routes `/api/ai/*` : les quatre existent.
- **Ne pas louer de GPU** tant que l'AUC est à 0,504. Le goulot n'est pas la vitesse
  d'entraînement, c'est l'absence de signal.
- **Ne pas remplacer** `packages/llm/local.py` : l'étendre.

---

## 6. Risques identifiés

| Risque | Nature | Mitigation |
|---|---|---|
| Le NLP n'apporte aucun alpha incrémental | probable | le mesurer AVANT de l'intégrer ; poids 0 assumé |
| Le registry ajoute de la cérémonie sans usage | réel | le brancher sur `train_model.py` dès le premier jour |
| Ollama sur 16 Go ≤ 7,5 Go de budget | contrainte dure | un seul modèle actif, cache borné, mesure RAM réelle |
| Une instance GPU oubliée | financier | double protection, testée |
| `packages/mlops` importe `execution` | sécurité | test d'isolation du graphe de dépendances |
