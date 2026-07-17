#!/usr/bin/env bash
# Démarre Quant Terminal EN UNE COMMANDE : met à jour le code, tue les vieux process,
# lance l'API (en arrière-plan) puis le front. Plus besoin de 3 commandes/fenêtres.
#   make start        (ou : bash scripts/start.sh)
# Variables surchargeables : QUANT_PRICE_DB, QUANT_HISTORY_DAYS, QUANT_NO_UPDATE=1 (saute le git reset),
# QUANT_REFRESH=1 (lance aussi make daily + ingest-crypto avant de démarrer).
set -uo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
source .venv/bin/activate 2>/dev/null || true

export QUANT_PRICE_DB="${QUANT_PRICE_DB:-$HOME/Desktop/YAHOO.db}"
export QUANT_FUND="${QUANT_FUND:-yf}"
export QUANT_NEWS="${QUANT_NEWS:-1}"
export QUANT_HISTORY_DAYS="${QUANT_HISTORY_DAYS:-4015}"
# Sources crypto/marchés GRATUITES (sans clé) — ON par défaut (comme en CI/`make site`) ;
# mettre QUANT_CRYPTO=0 etc. pour couper (ex. hors-ligne). Best-effort : n/d si injoignable.
export QUANT_CRYPTO="${QUANT_CRYPTO:-1}"               # cockpit crypto (/crypto)
export QUANT_PREDMKT="${QUANT_PREDMKT:-1}"             # marchés de prédiction (/macro)
# QUANT_CORE_SPEC / QUANT_DD_TARGET : respectés s'ils sont définis dans l'environnement (sinon défaut code).

BRANCH="claude/clever-lovelace-ognwya"
if [ "${QUANT_NO_UPDATE:-0}" != "1" ]; then
  echo "→ Mise à jour du code (origin/$BRANCH)…"
  git fetch origin >/dev/null 2>&1 && git reset --hard "origin/$BRANCH" >/dev/null 2>&1 && echo "  ✓ à jour" || echo "  ⚠ maj ignorée (hors-ligne ?)"
fi

echo "→ Arrêt des anciens process (API/front)…"
pkill -f "uvicorn apps.api.main" 2>/dev/null || true
lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null || true
lsof -ti:3000 2>/dev/null | xargs kill -9 2>/dev/null || true

if [ "${QUANT_REFRESH:-0}" = "1" ]; then
  echo "→ Maj des cours (make daily + crypto)…"
  python scripts/ingest_prices.py --daily || true
  python scripts/ingest_crypto.py || true
fi

mkdir -p logs
echo "→ Démarrage de l'API en arrière-plan (logs/api.log)…  build initial ~1-3 min"
nohup python -m uvicorn apps.api.main:app >logs/api.log 2>&1 &
echo "  PID API : $!"

echo "→ Démarrage du site (Ctrl+C arrête le SITE ; l'API continue en fond)…"
cd apps/web
npm install >/dev/null 2>&1 || true
echo "  Ouvre http://localhost:3000  (laisse ~1-3 min au 1er build de l'API)"
npm run dev
