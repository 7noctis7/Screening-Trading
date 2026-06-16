# 00 — INDEX (carte du projet)

> Mémoire = source de vérité. **Lire avant toute action, mettre à jour après chaque session.**

## Mission
Système de screening & trading systématique multi-actifs (actions, ETF, forex, crypto,
commodities, indices), niveau institutionnel, 100 % OSS. **Paper par défaut.**
Priorités : robustesse > maintenabilité > gestion du risque > recherche d'alpha > produit.

## Rituel de session (sans qu'on le redemande)
1. Lire `00_INDEX` → **`01_ARCHITECTURE` (les 2 diagrammes)** → `04_JOURNAL` (3 dernières) → `03_TODO`.
2. Reformuler en 3 lignes : où en est le projet, prochaine priorité (situer la tâche dans le schéma).
3. Exécuter par petits incréments testés.
4. Clôturer : maj `03_TODO`, entrée datée `04_JOURNAL`, log `02_DECISIONS`, **maj diagrammes si l'archi a changé** + miroir Notion, push.
5. Laisser le projet reprenable par une autre instance (schéma à jour = garantie).

## Carte des fichiers
| Fichier | Rôle |
|---|---|
| `01_ARCHITECTURE.md` | **Schéma vivant** (Mermaid), modules, conventions, état d'implémentation |
| `02_DECISIONS.md` | ADR — 1 entrée par choix |
| `03_TODO.md` | Backlog priorisé P0/P1/P2 |
| `04_JOURNAL.md` | Log daté de chaque session |
| `05_DATA_SOURCES.md` | APIs, clés, quotas, schémas |
| `06_STRATEGIES.md` | Specs des stratégies |
| `07_RISK_POLICY.md` | Règles de risque (trade + portefeuille) |
| `08_DATA_MODEL.md` | Schéma DB, couches, lineage |
| `09_RESEARCH.md` | Notes de lecture appliquées (concept → application) |
| `10_BACKTEST_RESULTS.md` | Résultats datés + hash de config |
| `11_DESIGN_SYSTEM.md` | Tokens UI, composants |
| `12_FACTORS.md` | Définitions des facteurs |

## État actuel
**Session 1 terminée** — tranche verticale runnable (data→backtest→métriques), 21 tests verts. Prochaine priorité : **Storage DuckDB + persistance journal + contrats pandera**.
