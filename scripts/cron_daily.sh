#!/usr/bin/env bash
# Mise à jour quotidienne automatique : prix réels (incrémental) → ML/snapshot → terminal.
# Best practices : idempotent (append, jamais d'écrasement), échoue proprement, journalise.
#
# Installation (macOS / Linux) :
#   crontab -e   puis ajouter (tous les jours à 22h30, après clôture US) :
#     30 22 * * 1-5 /Users/thierryfanlo/Screening-Trading/scripts/cron_daily.sh >> /tmp/quant_daily.log 2>&1
#   ou, sur macOS, via launchd (cf. docs/REAL_DATA.md).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# venv si présent (sinon python système)
# shellcheck disable=SC1091
[ -f .venv/bin/activate ] && source .venv/bin/activate

echo "[$(date '+%Y-%m-%d %H:%M:%S')] maj quotidienne — début"
python scripts/ingest_prices.py --daily            # backfill incrémental idempotent
python apps/web/preview/build_interactive.py        # régénère le terminal autonome
echo "[$(date '+%Y-%m-%d %H:%M:%S')] maj quotidienne — OK"
