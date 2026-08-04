# HANDOFF — prompt de reprise pour un nouvel agent IA

> Copie **tout le bloc ci-dessous** dans ton nouvel agent. Il est auto-suffisant et
> pointe vers la mémoire vivante du projet (CLAUDE.md, SKILL.md, vault/). Tenu à jour
> à chaque passation — la vérité opérationnelle reste le `vault/` et ce fichier.

```
Tu reprends « Quant Terminal » — un terminal de screening & trading systématique
multi-actifs, open-source, 0 €, PAPER par défaut, front statique GitHub Pages.
Repo GitHub : 7noctis7/Screening-Trading. Développeur solo (Thierry, français).

── RITUEL OBLIGATOIRE AVANT D'AGIR (sans qu'on te le redemande) ──
1. Lis dans l'ordre : CLAUDE.md (racine) → SKILL.md (racine, la méthode transmise) →
   vault/00_INDEX.md → vault/01_ARCHITECTURE.md → vault/04_JOURNAL.md (3 dernières
   sessions) → vault/03_TODO.md.
2. Reformule en 3 lignes : état du projet + prochaine priorité.
3. Agis par petits incréments TESTÉS (make test avant tout commit).
4. Clôture : maj 03_TODO + entrée datée 04_JOURNAL (+ ADR dans 02_DECISIONS si choix
   structurant), puis PR.

── GARDE-FOUS À NE JAMAIS ENFREINDRE ──
- PAPER par défaut. Aucun ordre réel sans `--live --yes` ET clés API présentes.
- Cloud (GitHub Actions) = PAPER POUR TOUJOURS. Jamais de clés réelles en CI publique.
- Pousser UNIQUEMENT sur la branche `claude/clever-lovelace-ognwya` (jamais `main` direct).
- Déploiement = PR → squash-merge → resync branche (git fetch origin main &&
  git reset --hard origin/main && git push --force). Ne pas ouvrir de PR sans qu'on le
  demande.
- Ne JAMAIS committer : .env, *.db, .cache/, site/, apps/web/public/{data,reports}.
- Repo PUBLIC : aucune donnée confidentielle. Positions courtier réelles = local-only.
- Fichiers < 400 lignes, fonctions < 50 lignes (un hook le bloque — refactorer, ne pas
  contourner). Nouvelle stratégie/indicateur = 1 fichier plugin, jamais toucher le cœur.
- MANDAT DONNÉES-RÉELLES : toute calibration/seuil vient de la DB/journal RÉELS. Données
  insuffisantes → dire « UNCALIBRATED », JAMAIS inventer. Synthétique autorisé UNIQUEMENT
  dans tests/.
- Ne jamais écrire l'identifiant de modèle dans un commit/PR/commentaire/artefact.

── PHILOSOPHIE (le wedge du projet) ──
L'honnêteté EST le produit. Gate à 4 étages (placebo → DSR → PBO/CSCV → sabotage), les
hypothèses rejetées sont PUBLIÉES sur /echecs. Priorité : robustesse > maintenabilité >
gestion du risque > alpha > produit. Un joli chiffre non prouvé vaut moins qu'un « je ne
sais pas » honnête.

── ÉTAT AU 2026-07-20 ──
- PR #320 + #321 mergées. Suite : 828 tests verts.
- VERDICT HONNÊTE du backtest preset : Sharpe 1,71 / Sortino 4,25 / maxDD −4,7 % / CAGR
  27,8 % MAIS DSR 34 % → PAS un edge prouvé (c'est du bêta bien géré, pas de l'alpha).
  Fill t+1 neutre (pas de look-ahead). Survivorship Δ≈0 mais SOUS-ÉCHANTILLONNÉ (7
  délistés seulement) — non concluant.
- Compte paper réel : −5,7 % mi-juin dû à un bug de rachat BTC en boucle, CORRIGÉ le 8/7.
  Portefeuille stable depuis.
- Deadline forçante : RDV paper 2026-08-06 = besoin de N≥20 round-trips réels réconciliés
  (make rdv-paper doit sortir GO, pas INSUFFISANT).

── ROADMAP OUVERTE (priorité = RDV 06/08) ──
XL-1 · Élargir les délistés (liste historique de composition d'indice) pour que le test
       de survivorship ait du mordant, puis publier le Δ Sharpe sur /echecs.
XL-2 · Refactorer les god-objects apps/api/snapshot.py (~2500 l) + main.py (~990 l) en
       modules — PAR TRANCHES, jamais big-bang.
L-1 · Accumuler le track record paper réel (N≥20 round-trips) — le vrai juge.
L-2 · Gater l'edge DD÷1,6 au PBO + brancher VaR-backtest sur le rail prod.
L-3 · Fusion pages front (/live+/trades→/positions ; /portfolio→/risk) — vérif visuelle.
L-4 · ML : soit gater proprement (CV CALENDAIRE, Brier OOS), soit dégrader en indicateur.
M · Attribution par actif + « pourquoi » par round-trip sur le front ; corriger le seuil
    trop serré (4 j) de verify-journal (fausse alerte sur cadence mensuelle).

── COMMANDES CLÉS ──
make test (avant tout commit) · make start (API+front local) · make site (aperçu mobile) ·
make preset-lab (labo Sharpe/survivorship, données réelles) · make rdv-paper (verdict GO) ·
make verify-journal · make vault-sync · make brief (état projet) · make audit.

Travaille en français. Économe (quota utilisateur limité). Toujours : PR → squash-merge →
resync, jamais de push direct sur main.
```

## Ce que l'agent ne trouvera PAS dans le repo (à lui fournir séparément)
- **Accès GitHub** : droit de push sur `claude/clever-lovelace-ognwya` + merge des PR.
- **`.env` local** : clés Alpaca paper, `FRED_API_KEY`, `HF_TOKEN`, `NOTION_TOKEN`.
  JAMAIS dans le repo ni dans un prompt — transmettre hors bande.
- **Bases de prix locales** (`data/*.db`) : reconstructibles via `make hf-pull` (cache
  public) puis `make daily`.
