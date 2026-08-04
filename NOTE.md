# NOTE — passation du projet (dernière maj : 2026-07-20)

> Note de relève, lisible par l'humain **et** le nouvel agent IA. Pour reprendre le
> projet : lire **d'abord** cette note, puis suivre `docs/HANDOFF.md` (le prompt de
> reprise à coller dans l'agent). La mémoire vivante reste le dossier `vault/`.

## Le projet en une ligne
**Quant Terminal** — screening & trading systématique multi-actifs, open-source, 0 €,
**paper par défaut**, front statique GitHub Pages. Front Next.js + API FastAPI.
En ligne : https://7noctis7.github.io/Screening-Trading/

## Où est quoi
| Besoin | Fichier / dossier |
|---|---|
| Règles + garde-fous (auto-chargé) | `CLAUDE.md` (racine) |
| Méthode de travail transmise | `SKILL.md` (racine) |
| **Prompt de reprise pour un agent IA** | `docs/HANDOFF.md` |
| Mémoire vivante (index, archi, journal, TODO, décisions) | `vault/` |
| Comment installer / lancer | `INSTALL.md`, `README.md` |
| Cœur backend | `apps/api/` (snapshot.py, main.py), `packages/` |
| Front | `apps/web/` |
| Recherche / gate d'honnêteté | `packages/research/`, `packages/portfolio/` |

## Comment faire tourner le projet
**En local :** `make setup` (une fois) → `make start` (API+front, localhost:3000) ·
`make site` (aperçu mobile, localhost:8080) · `make test` (avant tout commit).
**En ligne :** automatique — le site se reconstruit à chaque push sur `main` + chaque
jour ouvré ; le paper cloud tourne lun-ven (`.github/workflows/paper.yml`). Forcer le
site : GitHub → Actions → workflow `pages` → Run workflow.

## État au 2026-07-20 (à jour)
- PR #320 + #321 mergées ; suite de tests **828 verts**.
- **Verdict honnête du backtest** : Sharpe 1,71 · Sortino 4,25 · maxDD −4,7 % · CAGR
  27,8 % — MAIS **DSR 34 % → edge NON prouvé** (bêta bien géré, pas d'alpha). Fill t+1
  neutre (aucun look-ahead). Survivorship non concluant (7 délistés = sous-échantillonné).
- **Compte paper réel** : le −5,7 % de mi-juin venait d'un bug de rachat BTC en boucle,
  **corrigé le 8/7** ; portefeuille stable depuis. Ce n'est pas la stratégie qui déçoit.
- **Deadline** : RDV paper **2026-08-06** = il faut **N≥20 round-trips réels** réconciliés
  (`make rdv-paper` doit sortir GO). C'est le vrai juge, pas le backtest.

## Prochaines priorités (détail dans `vault/03_TODO.md`)
1. **L-1** — accumuler le track record paper réel (N≥20) avant le 06/08.
2. **XL-1** — élargir la liste de délistés pour un vrai test de survivorship, publier le
   Δ Sharpe sur `/echecs`.
3. **XL-2** — refactorer les god-objects `snapshot.py`/`main.py` par tranches.
4. **L-2/3/4, M** — gate PBO sur l'edge, fusion pages front, ML CV calendaire, attribution
   par actif (voir TODO).

## À transmettre au nouvel agent HORS du repo (jamais committé)
Accès GitHub (push `claude/clever-lovelace-ognwya` + merge PR) · `.env` local (clés Alpaca
paper, FRED, HF, Notion) · les bases `data/*.db` se reconstruisent via `make hf-pull` + `make daily`.
