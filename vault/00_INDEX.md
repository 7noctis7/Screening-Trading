# 🧠 00 — INDEX (tableau de bord)

> Mémoire = source de vérité. **Lire avant toute action, mettre à jour après chaque session.**
> Page d'accueil du cerveau : démarre toujours ici.

## 🚀 Accès rapide (clique un lien)
- 🏛️ [[01_ARCHITECTURE]] — schéma vivant, modules, conventions
- 🧭 [[02_DECISIONS]] — journal des choix (ADR)
- ✅ [[03_TODO]] — backlog priorisé (commence ta session ici)
- 📓 [[04_JOURNAL]] — log daté (lis les 3 dernières entrées)
- 🔌 [[05_DATA_SOURCES]] · 📈 [[06_STRATEGIES]] · 🛡️ [[07_RISK_POLICY]]
- 🗃️ [[08_DATA_MODEL]] · 🔬 [[09_RESEARCH]] · 📊 [[10_BACKTEST_RESULTS]]
- 🎨 [[11_DESIGN_SYSTEM]] · 🧮 [[12_FACTORS]]

## Mission
Screening & trading systématique multi-actifs (actions, ETF, forex, crypto, commodities, indices),
niveau institutionnel, 100 % OSS. **Paper par défaut.**
Priorités : robustesse > maintenabilité > gestion du risque > recherche d'alpha > produit.

## 🔁 Rituel de session (sans qu'on le redemande)
> Auto-chargé : `CLAUDE.md` (racine du repo) rappelle ce rituel + les garde-fous à **chaque** session
> Claude Code. Skills : `/deploy`, `/audit-secrets`, `/company-note`, `/close-session` (dans `.claude/commands/`).
1. **Avant** : [[00_INDEX]] → [[01_ARCHITECTURE]] (les 2 diagrammes) → [[04_JOURNAL]] (3 dernières) → [[03_TODO]].
2. Reformuler en 3 lignes : où en est le projet, prochaine priorité (situer la tâche dans le schéma).
3. **Pendant** : exécuter par petits incréments testés.
4. **Après (clôture)** : maj [[03_TODO]], entrée datée [[04_JOURNAL]], log [[02_DECISIONS]] si choix
   structurant, maj des diagrammes si l'archi a changé, miroir Notion, push. → skill **`/close-session`**.
   (En auto : le **cron** régénère chaque jour le journal/attribution/post-mortems via `make vault-sync`.)
5. Laisser le projet reprenable par une autre instance (schéma à jour = garantie).

## ✍️ Ce que TU édites vs ce qui s'écrit TOUT SEUL
> Ne modifie jamais un fichier auto-généré : il est écrasé au prochain run. Pour annoter une société,
> crée une note séparée qui pointe vers la sienne (ex. `[[AAPL]]`).

| ✍️ Manuel (toi) | 🤖 Auto-généré — ne pas éditer | Commande |
|---|---|---|
| [[00_INDEX]] · [[01_ARCHITECTURE]] · [[02_DECISIONS]] · [[03_TODO]] · [[04_JOURNAL]] · [[06_STRATEGIES]] · [[07_RISK_POLICY]] · [[09_RESEARCH]] | `Performance_Report.md` | `make analytics` |
| | `04_Companies/` (notes société `#company`) | `make reports` |
| | `04_Companies/_TOP200.md` | `make watchlist` |
| | journal du jour · attribution · post-mortems | `make vault-sync` |

## ⌨️ Raccourcis Obsidian essentiels
| Raccourci | Action |
|---|---|
| `Cmd/Ctrl + O` | aller à une note (quick switcher) |
| `Cmd/Ctrl + Shift + F` | recherche plein texte dans tout le vault |
| `Cmd/Ctrl + clic` | suivre un lien `[[...]]` |
| `[[` | créer un lien vers une note |
| `#` | poser un tag (ex. `#company`, `#decision`) |
| icône graphe (haut-gauche) | **Graph view** — la carte de tes idées |
| `Cmd/Ctrl + P` | palette de commandes |

Plugins cœur à activer (Settings → Core plugins) : Graph view · Backlinks · Outgoing links · Outline · Tag pane · Quick switcher · Search.

## 🌐 En ligne (PWA gratuite)
**https://7noctis7.github.io/Screening-Trading/** — front complet en statique, données réelles,
reconstruit chaque jour ouvré par GitHub Actions. Mac éteint, 0 €. Positions réelles **local-only**.

## 📍 État actuel
**2026-06-21** — PWA mobile **en ligne et fonctionnelle** (données réelles, historique 2015, notes HTML,
thème clair lisible, menu en tiroir). Pipeline statique durci (NaN-safe, abort si dump vide, lockfile
versionné). Sécurité : audit propre + gitleaks CI + `safe_pickle` + CORS verrouillé. Contexte agent :
`CLAUDE.md` racine + skills. Prochaine priorité : tunnel privé optionnel (positions mobiles) +
couverture fondamentale réelle en CI.
