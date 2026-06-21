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

echo "→ [1/2] Watchlist + top 200 (config/mobile_universe.csv + rapport Obsidian)…"
"$PY" scripts/build_watchlist.py || echo "  (watchlist ignorée — on continue)"

echo "→ [2/2] Construction de la PWA (site/)…"
"$PY" scripts/build_site.py

URL="http://localhost:${PORT}"
echo "→ Site prêt sur ${URL}  (Ctrl+C pour arrêter)"
( sleep 1; (command -v open >/dev/null && open "$URL") || (command -v xdg-open >/dev/null && xdg-open "$URL") || true ) &
exec "$PY" -m http.server "$PORT" -d site
