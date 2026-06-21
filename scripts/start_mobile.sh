#!/usr/bin/env bash
# Tout-en-un MOBILE/EN LIGNE : régénère la watchlist + le top 200, construit la PWA (site/) avec tes
# données réelles, puis sert le site en local et l'ouvre dans le navigateur.
#   bash scripts/start_mobile.sh         (ou : make site)
# Ctrl+C arrête le serveur. Le vrai hébergement gratuit en ligne se fait via GitHub Pages (cf. docs/DEPLOY.md).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# venv si présent (sinon python système) — fournit "python" + les dépendances
# shellcheck disable=SC1091
[ -f .venv/bin/activate ] && source .venv/bin/activate
PY="$([ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)"
PORT="${PORT:-8080}"

# Base de prix réelle : on garde QUANT_PRICE_DB s'il est défini, sinon on tente des emplacements connus.
if [ -z "${QUANT_PRICE_DB:-}" ]; then
  for c in "$HOME/Desktop/YAHOO.db" "$HOME/YAHOO.db" "$ROOT/data/YAHOO.db" "$ROOT/data/market.db"; do
    [ -f "$c" ] && export QUANT_PRICE_DB="$c" && break
  done
fi
echo "→ Données : ${QUANT_PRICE_DB:-(aucune base trouvée → synthétique de démo)}"
export QUANT_FUND="${QUANT_FUND:-yf}"     # fondamentaux réels (yfinance) par défaut

# [1/2] Calcule la watchlist + top 200 (parcourt TOUT l'univers → 1-3 min). Skippable.
if [ "${SKIP_WATCHLIST:-0}" = "1" ] && [ -f config/mobile_universe.csv ]; then
  echo "→ [1/2] Watchlist : conservée (SKIP_WATCHLIST=1)."
else
  echo "→ [1/2] Watchlist + top 200 (parcourt tout l'univers, peut prendre 1-3 min)…"
  "$PY" scripts/build_watchlist.py || echo "  (watchlist ignorée — on continue)"
fi

# [2/2] Construit la PWA BORNÉE à l'univers mobile (rapide = exactement ce que verra le téléphone).
echo "→ [2/2] Construction de la PWA (univers mobile borné)…"
[ -f config/mobile_universe.csv ] && export QUANT_UNIVERSE="$ROOT/config/mobile_universe.csv"
"$PY" scripts/build_site.py

URL="http://localhost:${PORT}"
echo "→ Site prêt sur ${URL}  (Ctrl+C pour arrêter)"
( sleep 1; (command -v open >/dev/null && open "$URL") || (command -v xdg-open >/dev/null && xdg-open "$URL") || true ) &
exec "$PY" -m http.server "$PORT" -d site
