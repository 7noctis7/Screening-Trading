# AGENTS.md — instructions pour tout agent IA travaillant sur ce dépôt

> Ce fichier s'adresse à **toi**, agent, quelle que soit ta famille de modèle.
> Il est court volontairement. Le détail est dans `docs/GROK_BOT_HANDOFF.md`.

---

## 1. Avant ta première modification

```bash
cat vault/00_INDEX.md          # où est la mémoire du projet
cat vault/01_ARCHITECTURE.md   # ce qui existe et pourquoi
tail -80 vault/04_JOURNAL.md   # les 3 dernières sessions
cat vault/03_TODO.md           # les priorités en cours
make brief                     # tout ça en 30 s
```

**Ne pars jamais du principe que le code existant est faux parce qu'il te surprend.** Une grande
partie de ce qui ressemble à de la complexité inutile est une cicatrice de bug réel, documentée
en commentaire juste au-dessus. Lis le commentaire avant de simplifier.

---

## 2. Architecture — la version courte

```
data/ (local, jamais commité)
  → packages/data → packages/{screening,backtest,portfolio,research,...}
  → apps/api/snapshot.py  (assemble tout)
  → apps/api/main.py (FastAPI) → apps/web (Next.js)
  → scripts/run_live.py → packages/risk/order_gate.py → packages/execution/*_broker.py
```

**Il n'y a qu'un seul chemin qui envoie des ordres : `scripts/run_live.py`.**

---

## 3. Commandes

| Commande | Rôle |
|---|---|
| `make test` | 1160 tests — **avant tout commit** |
| `make lint` | ruff + mypy |
| `make start` | API + front → `localhost:3000` |
| `make brief` | état du projet |
| `make audit` / `make contracts` | intégrité des données (gates CI) |
| `make alpha-lab` / `make preset-lab` | labos de recherche |
| `make live` | **aperçu** des ordres — dry-run, rien n'est envoyé |
| `make live-go` | exécute en **paper** — exige `--live --yes` + clés |

---

## 4. Fichiers critiques — à ne pas modifier sans comprendre

| Fichier | Pourquoi il est critique |
|---|---|
| `packages/risk/order_gate.py` | Dernière barrière avant le courtier. Ne peut que réduire ou refuser. |
| `packages/execution/rebalance_plan.py` | Décide acheter/alléger/**solder**. Une liquidation part en quantité. |
| `packages/backtest/panel.py` | Fenêtre commune. **Ne jamais écrire `min(len(...))` à la place.** |
| `packages/execution/live_guards.py` | Kill-switch drawdown, veto des brokers illisibles. |
| `scripts/run_live.py` | Le seul chemin d'ordres. |
| `apps/api/snapshot.py` | Assemble tout le payload du site. |

---

## 5. Règles de modification — non négociables

1. **< 400 lignes par fichier, < 50 lignes par fonction.** Un hook PostToolUse le signale.
2. **Plugins** : nouvelle stratégie / indicateur / facteur / source = **un fichier
   auto-enregistré**. Ne jamais modifier le cœur pour ajouter une variante.
3. **Mandat données réelles.** Toute calibration, tout seuil, toute recommandation vient de la
   base ou du journal **réels**. Données insuffisantes → écrire **UNCALIBRATED**. Jamais inventer.
   Le synthétique est autorisé **uniquement** dans `tests/`, pour valider les mathématiques.
4. **Tout garde-fou publie son compteur de déclenchements et son effet moyen.** C'est la
   convention la plus importante du dépôt — voir §8.
5. **Jamais de `min(len(data[s]) for s in syms)`.** Utiliser `packages/backtest/panel`.
6. `make test` doit passer avant tout commit.

---

## 6. Sécurité

- **Jamais committer** : `.env`, `*.db`, `.cache/`, `site/`, `apps/web/public/{data,reports}`.
- **Dépôt PUBLIC.** Aucune donnée confidentielle. Les positions réelles du courtier sont
  local-only : le build CI n'a pas les clés.
- gitleaks tourne en CI **et** en pre-commit.
- Les clés API vivent dans l'environnement ou dans le navigateur de l'utilisateur (clé IA),
  jamais dans le code, jamais dans un log, jamais dans une réponse d'API.
- **Ne jamais écrire d'identifiant de modèle** dans un commit, une PR, un commentaire de code ou
  un artefact poussé. Chat uniquement.

---

## 7. Trading — ce que tu ne peux pas faire

**Paper par défaut. Aucun ordre réel sans `--live --yes` ET clés API présentes.**

Tu ne dois **jamais** :
- placer un ordre réel ;
- activer le mode live, ni écrire du code qui l'activerait ;
- supprimer ou contourner `--yes` ;
- élever une limite du portail de risque ;
- désactiver un kill-switch.

### Le portail de risque

`packages/risk/order_gate.py` s'insère après la stratégie et avant le courtier. Limites lues
**dans l'environnement seul** : `QUANT_RISK_MAX_WEIGHT` (0.20), `QUANT_RISK_MAX_POSITIONS` (40),
`QUANT_RISK_MAX_ORDER_PCT` (0.15), `QUANT_RISK_MAX_GROSS` (**1.00 = aucun levier**),
`QUANT_MIN_POSITION` (1000).

Deux principes à ne jamais inverser :
1. **Le portail ne peut que réduire ou refuser, jamais augmenter.**
2. **Un désengagement n'est jamais bloqué** — même compte saturé, même equity illisible.
   Un portail qui refuse une vente augmente le risque.

### L'IA n'est pas dans la chaîne

`packages/llm` n'est importé que par `apps/api/main.py`, pour générer du texte affiché.
`packages/intelligence` n'importe ni `packages.execution` ni `packages.risk`, et un test le
vérifie sur l'arbre syntaxique. **Ne casse pas cette séparation.**

---

## 8. La convention la plus importante du dépôt

Six fois en une session, ce projet a produit le même bug : **un garde-fou qui ne se déclenche
jamais tout en ayant l'air de fonctionner**. Un `mode == "real"` jamais vrai. Un plancher qui ne
gardait que les ouvertures. Une colonne servie pour une ligne sur quatre. Des séries macro mortes
affichées comme vivantes. Un `make start` sur une branche périmée imprimant « à jour ». Un
plancher de p-value qui rendait la correction de tests multiples impossible.

**Quand tu ajoutes un filtre, un seuil, une limite ou un veto : publie son compteur.**

Convention établie :
- **clé absente** = garde-fou désactivé ;
- **clé à 0** = actif mais jamais déclenché → ⚠️ ;
- **effet moyen ×1,000** = déclenché sans rien changer → ⚠️.

Un filtre qui n'a rien filtré en trois mois est soit inutile, soit cassé. Dans les deux cas, il
faut pouvoir le lire.

---

## 9. Market Intelligence / X Intelligence

Point d'entrée unique : `packages.intelligence.pipeline.qualifier()`.

Règles encodées, à ne pas contourner :
- une **opinion** ne devient jamais un fait, quelle que soit la source ;
- le **nombre d'abonnés** vaut au maximum 0,08 sur 1,00 ;
- un compte **non authentifié** est plafonné à 0,60 ;
- les niveaux **D et E ne confirment jamais** ;
- les **reprises d'une même origine** comptent pour une seule ;
- l'exigence de corroboration **croît avec l'impact** (1 / 2 / 3) ;
- **aucun** des 66 comptes de la watchlist n'est authentifié — ne pas le prétendre.

---

## 10. Sous-agents disponibles

`session-auditor`, `friction-clusterer`, `quant-critic`, `leakage-hunter`, `vault-architect`,
`db-auditor`. Tous en lecture seule. Les utiliser pour l'analyse lourde.

---

## 11. Clôture de session

Mettre à jour `vault/03_TODO.md`, ajouter une entrée datée dans `vault/04_JOURNAL.md`, un ADR
dans `vault/02_DECISIONS.md` si le choix est structurant, rafraîchir les diagrammes si
l'architecture a changé. Le skill `/close-session` fait tout ça.
