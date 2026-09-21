.PHONY: combler-mfe help install setup test lint demos start stop api api-dev api-lan web preview interactive ingest daily cron cron-install cron-uninstall tearsheet train backtest-ml backtest-weighting backtest-earnings backtest-breakout backtest-sentiment backtest-preset backtest-megacap index-core coeur-multi diag-coeur-qqq index-core-stress index-core-regime crypto-core ledger-sweep ingest-crypto diag-creneau diag-pv-latente diag-source-crypto calibrer-seuil ingest-mktcap preset-report calibrate-preset preset-lab alpha-lab screen repro kill-check log-alpha sync-alphas event-study event-study-smid backtest-pead-smid funding-study risk-check sensitivity paper-watch vault-lint certification crypto-cockpit crypto-brief regime-study breakout-study microstructure-poc vault-ask crypto-screen screen-niche list-db live live-sim live-go live-cron-install live-cron-uninstall completer-ouvertures reconcilier-journal annuler-ventes annuler-chronologie annuler-doublons annuler-doublons-ouverts diag-journal diag-surfermeture diag-fusion bench-backend verify-journal reparer-journal banc-swing turnover-audit rdv-paper slippage alerts-test ingest-macro bitmart-check clean mcp-tv mcp-selftest mcp-overlays vault-sync audit ingest-delisted reports watchlist site site-lite analytics brief vault-search hf-push hf-pull journal-pull journal-push notion-sync contracts supabase-kpis sync sync-garde sync-garde-commits labs regime-atr-lab deviation-lab deviation-lab-crypto ingest-crypto-intraday garde-fous up up-apres-sync
# PYTHON : utilise AUTOMATIQUEMENT le venv s'il existe (.venv/bin/python), sinon python3 système.
# Évite le piège « No module named numpy » quand le venv n'est pas activé. Surchargeable.
TICKER ?= AAPL
# LA BRANCHE DE DÉPLOIEMENT EST LA BRANCHE PUBLIÉE (21/09). Le défaut pointait une
# branche de travail : `make up` disait « à jour » sans dire de QUOI. Une autre
# branche reste possible explicitement — `make up BRANCHE=ma-branche` — mais ne doit
# jamais redevenir le défaut persistant.
BRANCHE ?= main
PYTHON ?= $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)
# Fichiers SUIVIS que la chaîne quotidienne réécrit d'elle-même : les mettre de côté à
# chaque `make sync` produirait un avertissement permanent, donc plus lu du tout.
# MÊME LISTE que `DONNEES_REGENEREES` (packages/mlops/manifest.py) — un test le vérifie.
# Elle est redite ici en dur POUR QUE `sync` NE DÉPENDE DE RIEN : c'est la cible qu'on
# lance quand l'environnement Python est cassé.
FICHIERS_REGENERES ?= config/mobile_universe.csv data/delisted.csv
help:             ## liste toutes les cibles avec leur rôle (référence : docs/COMMANDES.md)
	@grep -hE '^[a-z][a-z0-9-]*:.*##' $(MAKEFILE_LIST) \
	  | sed -E 's/^([a-z0-9-]+):[^#]*## *(.*)$$/\1|\2/' \
	  | awk -F'|' '{printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'
install:          ## installe les dépendances (uv) SOUS le verrou de constraints.txt
	@# `-c constraints.txt` n'est pas décoratif : sans lui, la machine qui ENTRAÎNE
	@# installe ce qui passe, pendant que la CI installe des versions figées. Deux
	@# environnements, deux modèles, et rien qui le signale. Mesuré le 17/09 : le verrou
	@# n'était appliqué QUE dans les trois workflows GitHub, jamais en local ni sur le VPS.
	@# MÊME PIÈGE QUE `verrou-regen`, ET JE NE L'AVAIS CORRIGÉ QUE LÀ-BAS : `uv` n'est
	@# pas sur le PATH du VPS (son venv a été créé autrement). Une cible d'installation
	@# qui suppose un outil absent est la pire de toutes — c'est celle qu'on lance quand
	@# rien ne marche encore. On crée le venv avec le module standard, puis tout passe
	@# par l'interpréteur de CE venv.
	@[ -x .venv/bin/python ] || python3 -m venv .venv
	@.venv/bin/python -m uv --version >/dev/null 2>&1 \
	  || .venv/bin/python -m pip install --quiet uv
	.venv/bin/python -m uv pip install -e ".[dev,data,quant,api,ml]" -c constraints.txt

verrou-regen:     ## régénère constraints.txt AVEC les extras d'entraînement (sur la machine qui entraîne)
	@# ET ON LE VÉRIFIE, DÉSORMAIS. Le 18/09, cette cible lancée depuis le Mac
	@# (Darwin/arm64, Python 3.12) a produit un verrou de 140 paquets qui a remplacé
	@# celui du VPS (Linux/x86_64, Python 3.14, 159 paquets). `make verrou` restait VERT
	@# des deux côtés : rien n'invitait à regarder. Une phrase d'avertissement ne
	@# s'exécute pas — la garde, si (QUANT_VERROU_FORCE=1 pour passer outre).
	$(PYTHON) scripts/verrou_regen_garde.py
	@# TOUT PASSE PAR $(PYTHON), l'interpréteur du projet — jamais par un binaire du PATH.
	@# Deux tentatives ont échoué en nommant un outil absent de la machine visée :
	@# `pip-compile` (pip-tools n'est pas une dépendance) puis `uv` (présent sur le poste
	@# de développement, ABSENT du VPS). `python -m uv` ne dépend que du venv, et la ligne
	@# ci-dessous l'y installe si besoin — donc la cible marche partout où le projet tourne.
	$(PYTHON) -m uv --version >/dev/null 2>&1 || $(PYTHON) -m pip install --quiet uv
	$(PYTHON) -m uv pip compile --extra api --extra data --extra quant --extra ml \
	  --extra sentiment -o constraints.txt pyproject.toml
	@echo "→ Verrou régénéré. DEUX gestes, dans cet ordre :"
	@echo "     1.  make install     # s'y conformer, puis  make verrou  pour le vérifier"
	@echo "     2.  git add constraints.txt && git commit && git push -u origin $(BRANCHE)"
	@echo "   NE PAS SAUTER LE 2. Mesuré le 17/09 : le verrou régénéré (159 paquets) a"
	@echo "   disparu au « make sync » suivant — reset --hard détruit ce qui n'est pas commité."
setup:            ## installation locale guidée (venv, détection YAHOO.db, build, cron) — 1 commande
	bash scripts/setup_local.sh
sync:             ## RÉCUPÈRE la branche publiée (main par défaut) sans conflit (`BRANCHE=x` pour déroger)
	@# La branche de dev est RÉÉCRITE à chaque déploiement (`reset --hard origin/main`
	@# puis `push --force`). Un `git pull` la voit donc divergée, tente une FUSION, et
	@# laisse des marqueurs `<<<<<<<` dans les sources — d'où des `SyntaxError` sur du
	@# code pourtant valide à l'origine. `fetch` + `reset --hard` est la seule opération
	@# correcte ici : la branche n'a jamais de commit local à préserver.
	@# `reset --hard` DÉTRUIT les modifications locales non commitées, sans rien dire.
	@# Mesuré le 17/09 : un `constraints.txt` régénéré la veille sur le VPS a disparu
	@# ainsi, et c'est `make verrou` qui l'a appris à son propriétaire — deux étapes
	@# plus tard, sous la forme d'un chiffre qui avait « régressé ». D'où `sync-garde`.
	@git merge --abort 2>/dev/null || true
	@git rebase --abort 2>/dev/null || true
	@$(MAKE) --no-print-directory sync-garde
	@git fetch origin $(BRANCHE)
	@git checkout $(BRANCHE) 2>/dev/null || git checkout -b $(BRANCHE) origin/$(BRANCHE)
	@$(MAKE) --no-print-directory sync-garde-commits
	@git reset --hard origin/$(BRANCHE)
	@echo "→ $(BRANCHE) alignée sur origin : $$(git log --oneline -1)"
	@n=$$(git stash list | wc -l | tr -d ' '); [ "$$n" = 0 ] || \
	  echo "⚠ $$n entrée(s) en attente dans git stash — « git stash pop » pour les récupérer."
sync-garde-commits: ## sauvegarde les COMMITS locaux non poussés avant le « reset --hard »
	@# LE MÊME DÉFAUT, PAR L'AUTRE PORTE (mesuré le 17/09, deux heures après le premier).
	@# `sync-garde` protège l'arbre de travail ; `reset --hard` détruit AUSSI les commits
	@# locaux. Scène vécue : le verrou régénéré a été commité, le `git push` a échoué faute
	@# d'authentification sur le VPS, et le `make up` suivant — qui appelle `sync` — a
	@# ramené HEAD sur origin. Le commit avait disparu, et rien ne l'avait dit. Un travail
	@# commité mais non poussé est du travail délibéré : il se sauvegarde, il ne s'efface
	@# pas. On ne bloque pas pour autant — `sync` reste la commande de secours.
	@n=$$(git rev-list --count origin/$(BRANCHE)..HEAD 2>/dev/null || echo 0); \
	 [ "$$n" != 0 ] || exit 0; \
	 ref="sauvegarde/$$(date -u +%Y%m%d-%H%M%S)"; \
	 git branch "$$ref" HEAD \
	   || { echo "✗ sauvegarde IMPOSSIBLE — sync INTERROMPU plutôt que de détruire."; exit 1; }; \
	 echo "⚠ $$n commit(s) local(aux) NON POUSSÉ(S) qu'un « reset --hard » allait détruire :"; \
	 git log --oneline origin/$(BRANCHE)..HEAD | sed 's/^/     /'; \
	 echo "→ sauvegardés sur la branche « $$ref »."; \
	 echo "  Les rejouer :  git cherry-pick origin/$(BRANCHE)..$$ref"; \
	 echo "  Les publier :  git push -u origin $$ref"
sync-garde:       ## met de côté (git stash) ce qu'un « reset --hard » détruirait — appelé par `sync`
	@# Une cible à part, SANS réseau : elle est éprouvée telle quelle par les tests.
	@# Tout en shell + git : `sync` doit marcher même quand le venv est cassé.
	@perdus=$$(git status --porcelain --untracked-files=no \
	    | cut -c4- | sed -e 's/.* -> //' -e 's/^"//' -e 's/"$$//'); \
	 for f in $(FICHIERS_REGENERES); do \
	   perdus=$$(printf '%s\n' "$$perdus" | grep -vxF "$$f" || true); done; \
	 perdus=$$(printf '%s\n' "$$perdus" | sed '/^$$/d'); \
	 [ -n "$$perdus" ] || exit 0; \
	 echo "⚠ modifications locales NON COMMITÉES qu'un « reset --hard » allait détruire :"; \
	 printf '%s\n' "$$perdus" | sed 's/^/     /'; \
	 printf '%s\n' "$$perdus" \
	   | xargs git stash push --quiet -m "avant-sync $$(date -u +%Y-%m-%dT%H:%M:%SZ)" -- \
	   || { echo "✗ mise de côté IMPOSSIBLE — sync INTERROMPU plutôt que de détruire."; exit 1; }; \
	 echo "→ mises de côté. Les relire : git stash show -p · les remettre : git stash pop"; \
	 echo "  Puis COMMITER : sinon le prochain make sync rejoue exactement cette scène."
labs:             ## les cinq bancs de mesure (candidats, sorties, taille, signaux, régime ATR)
	$(PYTHON) scripts/candidats_lab.py
	$(PYTHON) scripts/sortie_lab.py
	$(PYTHON) scripts/sizing_lab.py
	$(PYTHON) scripts/signal_lab.py
	$(PYTHON) scripts/regime_atr_lab.py
regime-atr-lab:   ## éprouve la règle « ATR > 200 % de sa moyenne 30 » AVANT toute bascule
	$(PYTHON) scripts/regime_atr_lab.py $(ARGS)
deviation-lab:    ## le motif déviation→reclaim→consolidation prédit-il ? (gate placebo + DSR)
	$(PYTHON) scripts/deviation_reclaim_lab.py $(ARGS)
# `--tf` n'est injecté QUE si ARGS n'en porte pas : sinon `ARGS="--tf 4h"` produisait
# `--tf 4h --tf 4h`. argparse garde le dernier, donc rien ne cassait — et c'est
# précisément le problème : une ligne de commande qui se contredit sans le dire.
deviation-lab-crypto: ## le MÊME banc, sur crypto 1h/4h (TF=1h|4h) — le seul intraday gratuit et complet
	$(PYTHON) scripts/deviation_reclaim_lab.py --source crypto $(if $(findstring --tf,$(ARGS)),,--tf $(or $(TF),4h)) $(ARGS)
test:             ## lance la suite de tests
	$(PYTHON) -m pytest -q
coverage:         ## couverture de tests réelle (pytest-cov) → terme + rappel des trous
	$(PYTHON) -m pytest -q --cov=packages --cov-report=term-missing
lint:             ## ruff + mypy
	ruff check packages apps && mypy packages
demos:            ## exécute les démos offline
	$(PYTHON) scripts/demo_backtest.py && $(PYTHON) scripts/demo_walkforward.py && \
	$(PYTHON) scripts/demo_macro_regime.py && $(PYTHON) scripts/demo_ml.py && \
	$(PYTHON) scripts/demo_paper_loop.py && $(PYTHON) scripts/demo_alerts.py && $(PYTHON) scripts/demo_ops.py
preview:          ## régénère les aperçus HTML du dashboard/portefeuille
	$(PYTHON) apps/web/preview/build_preview.py
start:            ## TOUT EN UNE COMMANDE : maj code + kill vieux process + API (fond) + site
	bash scripts/start.sh
audit-univers:    ## trie les symboles sans nom en périmés / vivants, sur les PRIX locaux (lecture seule)
	$(PYTHON) scripts/auditer_univers_perime.py

noms-univers:     ## comble les noms manquants des seeds depuis les fournisseurs (jamais devinés)
	$(PYTHON) scripts/completer_noms_univers.py $(ARGS)

balayage-ic:      ## BALAYE horizons x classes d'actifs, corrigé Benjamini-Hochberg (long)
	$(PYTHON) scripts/balayage_ic.py $(ARGS)

valider-nouveautes: ## VALIDE sur données RÉELLES les modules non branchés (lecture seule)
	$(PYTHON) scripts/valider_nouveautes.py $(ARGS)
ic-screening:     ## MESURE l'IC hors échantillon du score de sélection (long, à lancer à la main)
	$(PYTHON) scripts/mesurer_ic_screening.py $(ARGS)

up:               ## TOUT EN UNE : sync + relance des services + attente que le front réponde
	@$(MAKE) --no-print-directory sync
	@$(MAKE) --no-print-directory up-apres-sync

# Sous-cible relue dans le Makefile NOUVELLEMENT récupéré. Ne pas remettre ces commandes
# directement sous `up` : le make parent a analysé l'ancienne recette avant le `git reset`.
up-apres-sync:
	@bash scripts/verifier_service.sh --unite
	@echo "→ Arrêt des services, puis des orphelins qui tiendraient encore les ports…"
	@sudo systemctl stop quant-api quant-web 2>/dev/null || true
	@# `systemctl restart` ne tue QUE les processus du service. Un `next dev` orphelin d'une
	@# session SSH morte survit donc à toutes les relances, garde le port 3000, et le service
	@# boucle en échec pendant que le navigateur parle à l'orphelin (mesuré le 07/09 :
	@# PID 757591 tenait le port depuis des heures, service en « activating (auto-restart) »).
	@# On arrête d'abord, on nettoie ensuite, on démarre enfin — dans cet ordre.
	@bash scripts/stop_services.sh
	@echo "→ Démarrage des services (le front recompile)…"
	@sudo systemctl start quant-api quant-web
	@printf "→ Attente du front"; \
	 for i in $$(seq 1 90); do \
	   if curl -sf -o /dev/null "http://127.0.0.1:$${QUANT_WEB_PORT:-3000}/"; then echo; break; fi; \
	   printf "."; sleep 5; \
	 done; \
	 if ! curl -sf -o /dev/null "http://127.0.0.1:$${QUANT_WEB_PORT:-3000}/"; then \
	   echo; echo "✗ le front n'a pas répondu en 7 min — voir : tail -40 logs/quant-web.log"; exit 1; \
	 fi
	@bash scripts/verifier_service.sh

services:         ## installe API+front en services systemd (survivent à la déconnexion SSH)
	sudo bash scripts/install_services.sh
services-restart: ## relance les services après un `make sync` (reconstruit le front)
	sudo systemctl restart quant-api quant-web && systemctl --no-pager status quant-api quant-web | head -20
services-logs:    ## suit les logs des services
	journalctl -u quant-web -u quant-api -f
stop:             ## arrête l'API et le site (uvicorn + next dev)
	@bash scripts/stop_services.sh; echo "arrêté"
api:              ## lance l'API FastAPI (localhost) — STABLE, sans reload (évite l'OOM pendant make daily)
	$(PYTHON) -m uvicorn apps.api.main:app
api-dev:          ## API avec reload du CODE seulement (apps/packages) — ne surveille PAS data/ (dev)
	$(PYTHON) -m uvicorn apps.api.main:app --reload --reload-dir apps --reload-dir packages
api-lan:          ## lance l'API accessible depuis le téléphone (même Wi-Fi) → http://IP_DU_MAC:8000
	$(PYTHON) -m uvicorn apps.api.main:app --host 0.0.0.0 --port 8000
web:              ## lance le front Next.js
	cd apps/web && npm install && npm run dev
interactive:      ## génère la preview autonome (apps/web/preview/interactive.html)
	$(PYTHON) apps/web/preview/build_interactive.py
ingest:           ## backfill des prix réels (yfinance) → data/market.db
	$(PYTHON) scripts/ingest_prices.py --since 2015-01-01
daily:            ## mise à jour incrémentale quotidienne des prix réels
	$(PYTHON) scripts/ingest_prices.py --daily
cron:             ## maj quotidienne complète (prix + terminal) — à mettre en crontab/launchd
	bash scripts/cron_daily.sh
cron-install:     ## ACTIVE la maj quotidienne auto (macOS launchd / Linux crontab) — 1 commande
	bash scripts/install_cron.sh
cron-uninstall:   ## désactive la maj quotidienne automatique
	bash scripts/install_cron.sh --uninstall
tearsheet:        ## exporte un tear sheet de performance (out/tearsheet.html + .pdf si reportlab)
	$(PYTHON) scripts/export_tearsheet.py
train:            ## entraîne le modèle ML hors-ligne → models/ (serving découplé, ticket #2)
	$(PYTHON) scripts/train_model.py
backtest-ml:      ## backtest ML walk-forward point-in-time (conviction+ML vs technique vs bench)
	$(PYTHON) scripts/backtest_ml.py
backtest-weighting:  ## compare equipondere/inverse-vol/min-var/risk-parity (net de frais)
	$(PYTHON) scripts/backtest_weighting.py
backtest-earnings:   ## backtest PEAD (earnings drift, dates via yfinance)
	$(PYTHON) scripts/backtest_earnings.py
backtest-breakout:   ## backtest cassures Donchian + measure rule (Bulkowski)
	$(PYTHON) scripts/backtest_breakout.py
backtest-sentiment:  ## event-study : le signal sentiment a-t-il un edge ? (data/news.csv requis)
	$(PYTHON) scripts/backtest_sentiment.py
backtest-preset:     ## backtest walk-forward du preset best-practice + overlay vol gérée (tes données)
	$(PYTHON) scripts/backtest_preset.py
backtest-megacap:    ## top-N méga-caps (rotation classement) vs S&P/Nasdaq réels
	$(PYTHON) scripts/backtest_megacap.py
index-core:          ## sweep cœur(s) + preset (QQQ / top-10 méga-caps) sur la vraie data
	$(PYTHON) scripts/index_core_sweep.py $(ARGS)
coeur-multi:         ## cœur multi-actifs (QQQ+TLT+GLD) contre le cœur QQQ, règle écrite d'avance
	$(PYTHON) scripts/coeur_multi_actifs_lab.py $(ARGS)
diag-coeur-qqq:      ## le cœur QQQ de prod est-il l'ETF ou un indice non achetable ?
	$(PYTHON) scripts/diag_coeur_qqq.py $(ARGS)
index-core-stress:   ## stress-test BEAR : perte du portefeuille par ratio QQQ pendant les krachs
	$(PYTHON) scripts/index_core_stress.py $(ARGS)
index-core-regime:   ## allocation adaptative bull/range/bear (détection MM200 S&P) vs fixe
	$(PYTHON) scripts/index_core_regime.py $(ARGS)
crypto-core:         ## cœur crypto BTC + panier majeures (équivalent QQQ pour Bitmart)
	$(PYTHON) scripts/crypto_core_sweep.py $(ARGS)
ledger-sweep:        ## perf RÉALISTE (journal discret) par % QQQ × DD-target × rebalancement
	$(PYTHON) scripts/ledger_sweep.py $(ARGS)
ingest-crypto:       ## ingère les prix des top-N cryptos (yfinance) → data/crypto.db (prix RÉELS)
	$(PYTHON) scripts/ingest_crypto.py $(ARGS)
ingest-crypto-intraday: ## OHLCV crypto 1h + 4h (Binance, gratuit, sans clé) → data/crypto_intraday.db
	$(PYTHON) scripts/ingest_crypto_intraday.py $(ARGS)
diag-creneau:        ## à quelle heure exécuter : décompose le rendement nuit / séance
	$(PYTHON) scripts/diag_creneau.py $(ARGS)
diag-pv-latente:     ## combien de PV latente a été rendue, ligne par ligne (yo-yo chiffré)
	$(PYTHON) scripts/diag_pv_latente.py $(ARGS)
diag-source-crypto:  ## confronte chaque série crypto en base à une référence indépendante (Binance)
	$(PYTHON) scripts/diag_source_crypto.py $(ARGS)
calibrer-seuil:      ## calibre SEUIL_ECART sur le VRAI panneau (coût / sensibilité) — n'écrit rien
	$(PYTHON) scripts/calibrer_seuil_ecart.py $(ARGS)
ingest-mktcap:       ## ingère les market caps (yfinance) → data/market_caps.json (cœur cap-weighted)
	$(PYTHON) scripts/ingest_market_cap.py $(ARGS)
preset-report:       ## rapport HTML autonome du backtest preset (courbes + drawdowns) → out/preset_report.html
	$(PYTHON) scripts/export_preset_report.py
calibrate-preset:    ## calibre le preset (DD × top-K × bande) par Sharpe déflaté (anti-overfit)
	$(PYTHON) scripts/calibrate_preset.py
diag-alignement:     ## d'OÙ vient le gain de l'alignement par date ? (correction réelle vs tirage d'univers)
	$(PYTHON) scripts/diag_alignement.py
preset-lab:          ## labo Sharpe/Sortino : cap adaptatif + overlay risque, mesurés puis gatés
	$(PYTHON) scripts/preset_lab.py
alpha-lab:           ## labo d'ALPHA : 5 hypothèses pré-enregistrées passées au gate 4 étages
	$(PYTHON) scripts/alpha_lab.py
screen:              ## screener à filtres (config/screening.yaml) → candidats triés par z-score
	$(PYTHON) scripts/run_screen.py
repro:               ## manifeste de reproductibilité (git sha + config/data hash + env) → out/repro.json
	$(PYTHON) scripts/repro_manifest.py
kill-check:          ## kill-switch INTRADAY : drawdown réel vs seuil (cron N×/j, aucun ordre)
	$(PYTHON) scripts/kill_switch_check.py
log-alpha:           ## logue un essai d'hypothèse d'alpha (ledger anti p-hacking) — voir ARGS
	$(PYTHON) scripts/log_hypothesis.py $(ARGS)
sync-alphas:         ## propage le ledger vers le frontmatter des notes vault/08_Alphas/
	$(PYTHON) scripts/sync_alpha_notes.py
event-study:         ## event-study 1 ticker (TICKER=AAPL) ou PANIER (TICKERS="AAPL,MSFT,NVDA")
	$(PYTHON) scripts/event_study_cli.py --ticker $(TICKER) $(if $(TICKERS),--tickers $(TICKERS)) $(ARGS)
SMID ?= CROX,ELF,CELH,RMBS,POWI,AAON,SPSC,ASO,BOOT,CALM,SHAK,FN
event-study-smid:    ## PEAD sur small/mid-caps (moins couvertes → dérive candidate)
	$(PYTHON) scripts/event_study_cli.py --tickers "$(SMID)" --source earnings $(ARGS)
backtest-pead-smid:  ## backtest PEAD small/mid NET de coûts + gate DSR/PBO (le vrai juge)
	$(PYTHON) scripts/backtest_pead_smid.py $(ARGS)
funding-study:       ## event-study funding crypto (reversion) + placebo — gate avant backtest
	$(PYTHON) scripts/funding_study_cli.py $(ARGS)
risk-check:          ## exposition brute recommandée (drawdown taper × vol prévue) — edge prouvé
	$(PYTHON) scripts/risk_check_cli.py $(ARGS)
sensitivity:         ## sensibilité des seuils (screening Jaccard + régime) — anti sur-optim
	$(PYTHON) scripts/sensitivity_cli.py $(ARGS)
paper-watch:         ## watchdog dérive paper vs backtest (cron nocturne) — exit≠0 si dérive
	$(PYTHON) scripts/paper_watch.py $(ARGS)
banc-swing:          ## le moteur swing ICT vaut-il d'être branché ? (mesure, ne branche rien)
	$(PYTHON) scripts/banc_swing.py $(ARGS)
certification:       ## les modules disent-ils la vérité sur leur place ? (SHADOW vs atteignable en prod)
	$(PYTHON) scripts/certification_check.py $(ARGS)
vault-lint:          ## intégrité du vault (liens morts, orphelins, ADR en double)
	$(PYTHON) scripts/vault_lint.py $(ARGS)
crypto-cockpit:      ## cockpit crypto marché (cap, dominance, F&G, TVL, narratifs, movers)
	$(PYTHON) scripts/crypto_cockpit_cli.py $(ARGS)
crypto-brief:        ## note de marché crypto → Obsidian (vault/11_Crypto), contexte
	$(PYTHON) scripts/crypto_brief_cli.py $(ARGS)
vault-ask:           ## assistant RAG ancré sur le vault (réponse citée, 0 hallucination) Q="..."
	$(PYTHON) scripts/vault_ask.py "$(Q)" $(ARGS)
crypto-screen:       ## screener crypto en langage naturel (text-to-filter) Q="cap > 5md top 10"
	$(PYTHON) scripts/crypto_screen_cli.py "$(Q)"
regime-study:        ## le Fear & Greed est-il un signal contrarian BTC ? gate placebo
	$(PYTHON) scripts/regime_study_cli.py $(ARGS)
breakout-study:      ## les cassures de canal BTC prédisent-elles un rendement ? gate placebo
	$(PYTHON) scripts/breakout_study_cli.py $(ARGS)
microstructure-poc:  ## POC OFI + vPIN crypto en direct (Binance, sans clé) — collecteur Mac
	$(PYTHON) scripts/microstructure_poc.py --sym $(or $(SYM),BTCUSDT)
screen-niche:        ## audit d'exploitabilité d'un univers/niche (score 0-100) avant de s'engager
	$(PYTHON) scripts/screen_niche.py
list-db:             ## liste ce que contient YAHOO.db (classes/secteurs) → pour bâtir une vraie niche
	$(PYTHON) scripts/build_niche.py
live:             ## APERÇU des ordres du PROCHAIN run réel (equity + positions RÉELLES, aucun ordre)
	$(PYTHON) scripts/run_live.py $(ARGS)
live-sim:         ## SIMULE un portefeuille NEUF (capital imposé, détenu ignoré) — ne décrit pas le compte
	$(PYTHON) scripts/run_live.py --equity $(or $(EQUITY),10000)
live-go:          ## EXÉCUTE en paper (Alpaca paper + Bitmart) — clés API requises
	$(PYTHON) scripts/run_live.py --live --yes
live-cron-install:   ## ACTIVE le rebalancement PAPER auto quotidien (lun-ven, launchd/cron)
	bash scripts/install_live_cron.sh
live-cron-uninstall: ## désactive le rebalancement paper automatique
	bash scripts/install_live_cron.sh --uninstall
completer-ouvertures: ## reconstitue au journal les ACHATS que le courtier a exécutés (simulation par défaut) — À FAIRE AVANT reconcilier-journal
	$(PYTHON) scripts/completer_ouvertures.py $(ARGS)
frais-courtier:      ## frais RÉELS lus chez le courtier + l'identité qu'ils referment
	$(PYTHON) scripts/frais_courtier.py
reconstruire-journal: ## REBÂTIT le journal depuis les SEULS fills du courtier (simulation par défaut)
	$(PYTHON) scripts/reconstruire_journal.py $(ARGS)
reparer-journal:     ## LA commande de réparation du journal : chaîne complète, dans l'ordre, fail-closed
	@echo "→ 1/7 entrées manquantes (refuse d'écrire un prix que le marché n'a pas coté)"
	@$(MAKE) --no-print-directory completer-ouvertures ARGS=--appliquer
	@echo "\n→ 2/7 sorties : fermetures appariées aux fills réels"
	@$(MAKE) --no-print-directory reconcilier-journal ARGS=--appliquer
	@echo "\n→ 3/7 lots ouverts qui sont en fait des ventes"
	@$(MAKE) --no-print-directory annuler-ventes ARGS=--appliquer
	@echo "\n→ 4/7 chronologies impossibles"
	@$(MAKE) --no-print-directory annuler-chronologie ARGS=--appliquer
	@echo "\n→ 5/7 réalisé compté deux fois"
	@$(MAKE) --no-print-directory annuler-doublons ARGS=--appliquer
	@# ÉTAPE AJOUTÉE LE 18/09. `diag-journal` détectait les lots OUVERTS en double
	@# depuis le 03/09 et les imprimait ; aucun script ne les retirait — l'étape 5
	@# ne traite que les doublons de FERMETURE. Le doublon QQQ du 17/09 a donc
	@# survécu à trois passages de cette chaîne. Un défaut détecté sans remède reste.
	@echo "\n→ 6/7 lots OUVERTS enregistrés deux fois"
	@$(MAKE) --no-print-directory annuler-doublons-ouverts ARGS=--appliquer
	@echo "\n→ 7/7 vérification : l'écart doit être PETIT (identité comptable)"
	@$(MAKE) --no-print-directory diag-journal
reconcilier-journal: ## ferme les lots orphelins du journal avec les fills RÉELS (simulation par défaut)
	$(PYTHON) scripts/reconcilier_journal.py $(ARGS)
annuler-ventes:      ## retire les lots « ouverts » qui sont en fait des VENTES (simulation par défaut) — APRÈS reconcilier-journal
	$(PYTHON) scripts/annuler_ventes_inversees.py $(ARGS)
annuler-chronologie: ## retire les round-trips dont la sortie précède l'entrée (simulation par défaut)
	$(PYTHON) scripts/annuler_chronologie_impossible.py $(ARGS)
annuler-doublons:    ## retire les lots dont le « réalisé » double une correction nommée (simulation par défaut)
	$(PYTHON) scripts/annuler_doublons_correction.py $(ARGS)
annuler-doublons-ouverts: ## retire les lots OUVERTS enregistrés deux fois (simulation par défaut)
	$(PYTHON) scripts/annuler_doublons_ouverts.py $(ARGS)
combler-mfe:         ## calcule MFE/MAE sur les trades clos qui n'en ont pas (SIMULATION par défaut)
	$(PYTHON) scripts/combler_mfe.py $(ARGS)
diag-journal:        ## RÉCONCILIE le journal des round-trips avec la courbe du compte réel
	$(PYTHON) scripts/diag_journal_compte.py $(ARGS)
verify-journal:      ## vérifie que le cron paper ALIMENTE journal.db (legacy=0, cryptos, features) — BLOC 4
	$(PYTHON) scripts/verify_journal.py $(ARGS)
diag-surfermeture:   ## d'où vient l'écart quand le COURTIER détient ce que le journal ignore (lecture seule)
	$(PYTHON) scripts/diag_sur_fermeture.py $(ARGS)
turnover-audit:      ## coût réel du rebalancement quotidien (frais, durée, capture) — UNCALIBRATED si journal vide
	$(PYTHON) scripts/turnover_audit.py $(ARGS)
rdv-paper:           ## verdict GO/NO-GO mécanique du RDV 2026-08-06 (paper réel vs backtest)
	$(PYTHON) scripts/rdv_paper.py
bitmart-check:       ## diagnostic Bitmart LECTURE SEULE (verrous + connexion, zéro ordre) — BLOC 2
	$(PYTHON) scripts/bitmart_check.py
ingest-macro:        ## vintages ALFRED réels (PIT) → data/macro.db (FRED_API_KEY requis, gratuit)
	$(PYTHON) scripts/ingest_macro.py
alerts-test:         ## envoie une alerte de TEST sur les canaux configurés (Console + Telegram/Discord si clés .env)
	$(PYTHON) -c "from packages.common.env import load_env; load_env(); \
from packages.alerts.wiring import default_engine; from packages.alerts import Alert, Severity; \
e = default_engine(); e.emit(Alert('ops', Severity.WARNING, 'TEST alertes — si tu lis ceci sur Telegram/Discord, le filet ops est branché.', dedup_key='ops:test')); \
print('→ alerte émise sur', len(e.sinks), 'canal/canaux (Console seul = clés Telegram/Discord absentes du .env)')"
slippage:            ## slippage RÉEL mesuré (décision→fill) depuis journal.db — calibre le sabotage
	$(PYTHON) -c "from packages.research.exec_costs import measured_slippage; from packages.storage import SqliteTradeJournal; import json; print(json.dumps(measured_slippage(SqliteTradeJournal()), indent=2, ensure_ascii=False))"
mcp-tv:           ## lance le serveur MCP TradingView (overlays, Pine, alertes) — stdio, en parallèle de l'API/front
	$(PYTHON) -m packages.mcp_tradingview.server
mcp-selftest:     ## auto-vérif des outils MCP en mémoire (sans handshake) — liste + génère un Pine
	$(PYTHON) -c "from packages.mcp_tradingview import server as s; import json; \
print('outils:', [t['name'] for t in s.list_tools()]); \
print('pine ok:', s.call_tool('generate_pine_script', {'strategy_name':'selftest'})['pine'][:14])"
mcp-overlays:     ## calcule les cônes VaR/EVT (prix réels) + blackouts et les pousse au chart (API démarrée requise)
	$(PYTHON) scripts/mcp_populate_overlays.py
vault-sync:       ## régénère le coffre Obsidian (journal du jour, attribution, post-mortems) depuis YAHOO.db
	$(PYTHON) -m packages.reporting.obsidian
diag-fusion:      ## les bases de prix sont-elles d'accord ? désaccords mesurés par symbole
	$(PYTHON) scripts/diag_fusion_sources.py $(ARGS)
bench-backend:    ## SQLite vs DuckDB sur la LECTURE OHLCV — règle de décision écrite avant le run
	$(PYTHON) scripts/bench_backend_ohlcv.py $(ARGS)
audit:            ## audit PwC des bases de prix (complétude/exactitude/point-in-time) — make audit ARGS=--strict
	$(PYTHON) scripts/data_audit.py $(ARGS)
ingest-delisted:  ## détecte les titres délistés (barres trop anciennes) → data/delisted.csv (anti-biais du survivant)
	$(PYTHON) scripts/ingest_delisted.py $(ARGS)
reports:          ## pré-génère les notes d'analyse (top-conviction + positions) → out/notes/AAAA-MM-JJ
	$(PYTHON) scripts/generate_reports.py $(ARGS)
watchlist:        ## top 200 par note + watchlist fixe → config/mobile_universe.csv + rapport Obsidian (borne la PWA en ligne)
	$(PYTHON) scripts/build_watchlist.py $(ARGS)
site:             ## TOUT-EN-UN MOBILE (front COMPLET Next.js) : watchlist + données + export + serveur (http://localhost:8080)
	bash scripts/start_full.sh
site-lite:        ## variante LÉGÈRE sans Node (terminal autonome interactive.html) + serveur local
	bash scripts/start_mobile.sh
analytics:        ## rapport de perf QuantStats (Sortino/Calmar/Alpha-Beta vs QQQ) → vault/Performance_Report.md
	$(PYTHON) scripts/perf_report.py
alpha-lexique:    ## le lexique apporte-t-il un alpha ? (étude d'événement + placebo, sans LLM)
	$(PYTHON) scripts/alpha_lexique_lab.py $(ARGS)

news:             ## accumule le corpus de news datées (ARGS=--etat pour l'état seul)
	$(PYTHON) scripts/collecter_news.py $(ARGS)

verrou:           ## ce que constraints.txt NE couvre PAS pour l'entraînement
	$(PYTHON) scripts/verrou_env.py

registre:         ## registre des modèles : production, candidats, archives (ARGS=--rollback --motif "…")
	$(PYTHON) scripts/registre_modeles.py $(ARGS)

churn:            ## coût CUMULÉ des rebalancements en double (historique RÉEL du courtier)
	$(PYTHON) scripts/cout_churn.py $(ARGS)

garde-fous:       ## ce que les garde-fous d'exécution ont VRAIMENT fait (ARGS=--mode tout --jours 30)
	$(PYTHON) scripts/garde_fous.py $(ARGS)

brief:            ## brief unifié (priorités + journal + changements + audit) → stdout (ARGS=--write → vault/_BRIEF.md)
	$(PYTHON) scripts/daily_brief.py $(ARGS)
macro-verify:      ## vérifie que chaque identifiant FRED existe et publie encore (FRED_API_KEY requise)
	$(PYTHON) scripts/macro_verify.py
vault-search:     ## recherche sémantique locale du vault — make vault-search Q="ta question" (TF-IDF ; QUANT_EMBED=ollama)
	$(PYTHON) scripts/vault_search.py search "$(Q)" -k $(or $(K),5)
hf-push:          ## pousse le cache OHLCV (market+crypto) vers le dataset HuggingFace (HF_TOKEN requis)
	$(PYTHON) scripts/hf_cache.py push $(ARGS)
hf-pull:          ## reconstruit data/*.db depuis le cache HuggingFace public (sans token)
	$(PYTHON) scripts/hf_cache.py pull $(ARGS)
journal-pull:     ## récupère data/journal.db depuis le dataset HF PRIVÉ (HF_TOKEN requis)
	$(PYTHON) scripts/hf_journal.py pull
journal-push:     ## pousse data/journal.db vers le dataset HF PRIVÉ (HF_TOKEN requis)
	$(PYTHON) scripts/hf_journal.py push
notion-sync:      ## miroir Obsidian → Notion (NOTION_TOKEN + NOTION_PARENT requis) — ARGS pour cibler des fichiers
	$(PYTHON) scripts/notion_sync.py $(ARGS)
contracts:        ## gate contrats OHLCV (intégrité watchlist) — exit≠0 si violation (#10)
	$(PYTHON) scripts/contracts_check.py $(ARGS)
supabase-kpis:    ## pousse les KPIs du jour vers Supabase (SUPABASE_URL + SUPABASE_KEY requis) (#7)
	$(PYTHON) scripts/kpi_to_supabase.py
clean:
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null; rm -rf out
