# Contribuer

Projet solo à discipline institutionnelle — les contributions externes sont bienvenues mais gatées.

## Règles non négociables (cf. CLAUDE.md, source de vérité)
1. **`make test` vert avant tout commit** (pytest bloquant en CI).
2. **< 400 lignes/fichier, < 50 lignes/fonction** — un hook le signale, la CI aussi à terme.
3. **Plugins, pas de chirurgie** : nouvelle stratégie/indicateur/facteur/source = 1 fichier
   auto-enregistré (`packages/core/registry.py`), jamais modifier le cœur.
4. **Mandat données réelles** : toute calibration vient de données réelles ; insuffisant →
   « UNCALIBRATED ». Synthétique UNIQUEMENT dans `tests/`.
5. **Aucun signal en prod sans le gate 4 étages** : placebo (p<0,05) → DSR → PBO → sabotage.
   Les rejets sont PUBLIÉS (`/echecs`) — un négatif propre est une contribution valable.
6. **Point-in-time partout** — tout look-ahead est un bug P0 (voir `packages/common/pit_guard`).
7. Jamais de secret/`.env`/`*.db` dans un commit (gitleaks te bloquera).

## Flux
Fork → branche → PR vers `main`. La CI (pytest + gitleaks) doit être verte. Squash-merge.
Description de PR : quoi/pourquoi/tests, en français ou anglais.
