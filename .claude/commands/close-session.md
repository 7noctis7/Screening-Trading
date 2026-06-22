---
description: Clôture proprement une session de travail — met à jour le TODO et le JOURNAL du vault (+ DECISIONS si besoin), puis commit/push. À lancer en fin de session.
---

Exécute le **rituel de clôture** du projet (cf. `CLAUDE.md` + `vault/00_INDEX`). But : laisser le
projet reprenable par une autre instance, mémoire à jour.

1. **Récapituler** ce qui a été fait dans cette session (3-5 puces concrètes : changements, décisions, état).
2. **`vault/03_TODO.md`** : cocher/retirer ce qui est terminé, ajouter les nouvelles tâches découvertes
   (priorisées P0/P1/P2), remonter la prochaine priorité en tête.
3. **`vault/04_JOURNAL.md`** : ajouter une **entrée datée** en haut, format des entrées existantes
   (`## Session AAAA-MM-JJ — titre`, puis **Fait** / **Décidé** / **Prochaine étape**).
4. **`vault/02_DECISIONS.md`** : 1 entrée ADR **uniquement** si un choix structurant a été tranché.
5. **`vault/00_INDEX.md`** : mettre à jour la ligne « État actuel » (date + 1 phrase) si l'état a changé.
6. Si l'architecture a changé : mettre à jour les diagrammes de `vault/01_ARCHITECTURE.md`.
7. **Committer + pousser** sur `claude/clever-lovelace-ognwya` (message clair, sans identifiant de modèle).
   Si du code applicatif a aussi changé, enchaîner avec le skill `/deploy`.

Garde-fous : ne jamais éditer les fichiers auto-générés (`Performance_Report.md`, `04_Companies/`,
`_TOP200.md`) ; ne rien committer de sensible ; rester factuel dans le journal (ce qui est fait/testé).
