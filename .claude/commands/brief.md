---
description: Affiche le brief unifié du projet (priorités P0/P1, dernière entrée de journal, notes du vault modifiées, audit data) pour démarrer une session en 30 s.
---

Génère le **brief unifié** : `python scripts/daily_brief.py` (ou `make brief`).

Il agrège, sans dépendance externe :
- les **priorités** P0/P1 de `vault/03_TODO.md` ;
- la **dernière entrée** de `vault/04_JOURNAL.md` ;
- les **notes du vault modifiées** dans les dernières 24 h (git) ;
- un **résumé de l'audit data** (`scripts/data_audit.py`).

Usage : le lire en début de session pour reconstituer l'état (complète le rituel de `CLAUDE.md`).
`make brief ARGS=--write` l'enregistre dans `vault/_BRIEF.md` (gitignoré). Pour retrouver une note
précise plutôt qu'un survol : `make vault-search Q="ta question"` (recherche sémantique locale).
