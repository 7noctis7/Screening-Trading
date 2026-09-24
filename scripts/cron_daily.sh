#!/usr/bin/env bash
# Mise à jour quotidienne automatique : prix réels (incrémental) → ML/snapshot → terminal.
# Best practices : idempotent (append, jamais d'écrasement), échoue proprement, journalise.
#
# Installation (macOS / Linux) :
#   crontab -e   puis ajouter (tous les jours à 22h30, après clôture US) :
#     30 22 * * 1-5 /Users/vous/Screening-Trading/scripts/cron_daily.sh >> /tmp/quant_daily.log 2>&1
#   ou, sur macOS, via launchd (cf. docs/REAL_DATA.md).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# venv si présent (sinon python système)
# shellcheck disable=SC1091
[ -f .venv/bin/activate ] && source .venv/bin/activate

echo "[$(date '+%Y-%m-%d %H:%M:%S')] maj quotidienne — début"
python scripts/ingest_prices.py --daily            # backfill incrémental idempotent
python scripts/data_audit.py || true                # audit PwC des bases (complétude/exactitude/PIT)
python scripts/ingest_delisted.py || true           # met à jour data/delisted.csv (anti-biais survivant)
# CORPUS DE NEWS — un flux RSS ne se rejoue pas : chaque jour sans collecte est un jour
# perdu DÉFINITIVEMENT. C'est la seule tâche de la chaîne dont le coût augmente avec le
# retard, d'où sa place ici plutôt que dans un script qu'on lance quand on y pense.
python scripts/collecter_news.py --silencieux || true   # data/news.csv (append-only, daté)
# CHURN — mesure l'historique du courtier et DÉPOSE le rapport pour le site, qui ne peut
# pas l'appeler lui-même (pas de clés dans le build public). Sans ce passage quotidien, la
# courbe d'equity réelle s'afficherait sans annotation — donc comme si elle était saine.
python scripts/cout_churn.py >/dev/null \
  || echo "⚠️  cout_churn.py EN ÉCHEC — la courbe réelle s'affichera « churn non mesuré »"
# Gate optionnelle : QUANT_AUDIT=strict fait refuser au build tout prix à anomalie CRITIQUE.
# Le ré-entraînement ne doit pas faire tomber la chaîne (rapports, watchlist, miroirs),
# mais son échec doit se VOIR : `|| true` seul rendait la panne indétectable dans le log.
# Le champion précédent est conservé par le script lui-même (cf. `_mettre_de_cote`).
python scripts/train_model.py \
  || echo "⚠️  train_model.py EN ÉCHEC — modèle non ré-entraîné, champion précédent conservé"
# FLUX SOCIAL (onglet /x) — même raison que le corpus de news, et PLUS TRANCHANTE.
# L'aperçu public `t.me/s/<canal>` ne rend qu'une vingtaine de messages, et un miroir RSS
# guère plus. Sur un canal actif, une semaine sans ingestion est une semaine PERDUE
# DÉFINITIVEMENT : les messages sortent de la fenêtre et aucune relance ne les rattrape.
# C'est ce qui fait passer cette tâche de « à lancer quand on y pense » à « quotidienne ».
#
# Chaque source ne tourne que si elle est CONFIGURÉE — sans quoi le log se remplirait
# chaque jour d'un échec attendu, et un vrai échec s'y noierait. Mais la question se
# pose EN PYTHON (`--si-configuree`), et surtout PAS ici : `.env` n'est lu que par
# `packages/common/env.py`, donc un `[ -n "${QUANT_TG_CANAUX:-}" ]` serait toujours
# faux sous cron — dont l'environnement est nu — et sauterait les trois sources EN
# SILENCE, chaque nuit. Une garde écrite au mauvais étage ne protège de rien : elle
# éteint la tâche qu'elle était censée rendre propre, sans une ligne pour le dire.
python scripts/social_x_ingest.py --source telegram --si-configuree \
  || echo "⚠️  ingestion Telegram EN ÉCHEC — l'onglet /x se fige sur l'existant"
python scripts/social_x_ingest.py --source rss --si-configuree \
  || echo "⚠️  ingestion RSS EN ÉCHEC — miroir mort ? relancer make x-miroirs"
python scripts/social_x_ingest.py --source discord --si-configuree \
  || echo "⚠️  ingestion Discord EN ÉCHEC — jeton révoqué ou bot retiré du serveur ?"
python apps/web/preview/build_interactive.py        # régénère le terminal autonome
python scripts/mcp_populate_overlays.py --offline || true   # cônes VaR/EVT + blackouts → charts (best-effort)
python -m packages.reporting.obsidian || true               # coffre Obsidian : journal + attribution + post-mortems
python scripts/generate_reports.py || true                  # notes d'analyse (top-conviction + positions) datées
python scripts/build_watchlist.py || true                   # top 200 + watchlist → config/mobile_universe.csv + Obsidian
[ -n "${HF_TOKEN:-}" ] && python scripts/hf_cache.py push || true   # rafraîchit le cache OHLCV HF (si HF_TOKEN présent)
[ -n "${NOTION_TOKEN:-}" ] && python scripts/notion_sync.py || true # miroir Obsidian→Notion (si NOTION_TOKEN présent)
[ -n "${SUPABASE_URL:-}" ] && python scripts/kpi_to_supabase.py || true  # historique KPIs cloud (si Supabase configuré)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] maj quotidienne — OK"
