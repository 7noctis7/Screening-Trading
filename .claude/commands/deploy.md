---
description: Livre les changements en cours — tests, commit, PR, squash-merge, resync de branche, puis vérifie le déploiement GitHub Pages.
---

Procédure de livraison standard du projet (à suivre dans l'ordre, sans sauter d'étape) :

1. **Vérifier** l'état : `git status`, `git diff --stat`. Confirmer qu'aucun fichier sensible
   (`.env`, `*.db`, `.cache/`, `site/`, `apps/web/public/{data,reports}`) n'est mis en stage.
2. **Tester** : `make test` (ou un sous-ensemble ciblé `pytest tests/ -k "..."`). Ne pas continuer si rouge.
3. **Si le front change** : `cd apps/web && STATIC_EXPORT=1 NEXT_PUBLIC_STATIC=1 NEXT_PUBLIC_BASE_PATH=/Screening-Trading npm run build` pour valider la compilation.
4. **Committer** sur la branche `claude/clever-lovelace-ognwya` (jamais `main`), message clair, sans identifiant de modèle.
5. **Pousser** : `git push -u origin claude/clever-lovelace-ognwya` (retry x4 backoff si erreur réseau).
6. **PR → squash-merge** vers `main` (via les outils GitHub MCP). Ne créer une PR que si demandé/attendu.
7. **Resync** la branche :
   `git fetch origin main -q && git reset --hard origin/main -q && git push -u origin claude/clever-lovelace-ognwya --force`.
8. **Si `apps/`, `packages/`, `scripts/`, `config/` ou le workflow ont changé** : le merge déclenche
   le déploiement Pages. Vérifier le run `pages.yml` (build **et** deploy verts) et confirmer l'URL
   `https://7noctis7.github.io/Screening-Trading/`. Le scan `gitleaks` doit aussi être vert.

Garde-fous : paper par défaut, jamais de secret committé, ne pas renommer le compte GitHub pendant un run.
