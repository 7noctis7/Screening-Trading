#!/usr/bin/env bash
# Tout-en-un MOBILE — FRONT COMPLET (parité make start) : watchlist+top200 → données figées →
# export statique Next.js → serveur local + ouverture navigateur. Toujours exécuté depuis la racine.
#   bash scripts/start_full.sh   (ou : make site)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# shellcheck disable=SC1091
[ -f .venv/bin/activate ] && source .venv/bin/activate
PY="$([ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)"
PORT="${PORT:-8080}"

# base de prix réelle
if [ -z "${QUANT_PRICE_DB:-}" ]; then
  for c in "$HOME/Desktop/YAHOO.db" "$HOME/YAHOO.db" "$ROOT/data/YAHOO.db" "$ROOT/data/market.db"; do
    [ -f "$c" ] && export QUANT_PRICE_DB="$c" && break
  done
fi
echo "→ Données : ${QUANT_PRICE_DB:-(aucune base → synthétique de démo)}"
export QUANT_FUND="${QUANT_FUND:-yf}"
export QUANT_MAX_REPORTS="${QUANT_MAX_REPORTS:-24}"   # notes pré-générées en local (rapide ; CI = 60)
export QUANT_NO_LLM=1                                  # pas d'appel LLM pendant le build (anti-blocage)

# [1/3] watchlist + top 200 (parcourt tout l'univers ~1-3 min) — skippable
if [ "${SKIP_WATCHLIST:-0}" = "1" ] && [ -f config/mobile_universe.csv ]; then
  echo "→ [1/3] Watchlist conservée (SKIP_WATCHLIST=1)."
else
  echo "→ [1/3] Watchlist + top 200 (peut prendre 1-3 min)…"
  "$PY" scripts/build_watchlist.py || echo "  (watchlist ignorée — on continue)"
fi

# dépendances web : (ré)installe si absentes OU PÉRIMÉES (ex. après ajout de three/fiber)
# `npm ls three` échoue si une dépendance déclarée manque → on réinstalle.
if [ ! -d apps/web/node_modules ] || ! ( cd apps/web && npm ls three >/dev/null 2>&1 ); then
  echo "→ (Ré)installation des dépendances web (manquantes ou périmées)…"
  ( cd apps/web && (npm ci || npm install) )
fi

# [2/3] build statique borné à l'univers mobile (= ce que verra le téléphone), basePath vide en local
echo "→ [2/3] Export du front complet Next.js (univers mobile)…"
[ -f config/mobile_universe.csv ] && export QUANT_UNIVERSE="$ROOT/config/mobile_universe.csv"
NEXT_PUBLIC_BASE_PATH="" "$PY" scripts/build_static_site.py

# [3/3] serveur local + ouverture
URL="http://localhost:${PORT}"
echo "→ [3/3] Site prêt sur ${URL}  (Ctrl+C pour arrêter)"
( sleep 1; (command -v open >/dev/null && open "$URL") || (command -v xdg-open >/dev/null && xdg-open "$URL") || true ) &
exec "$PY" -m http.server "$PORT" -d site
