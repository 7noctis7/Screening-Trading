#!/usr/bin/env bash
# Installation locale en une commande (macOS / Linux) — idempotent, sûr.
#   bash scripts/setup_local.sh
# Fait : venv + dépendances · détecte YAHOO.db et exporte QUANT_PRICE_DB (dans le profil shell)
#        · construit le terminal autonome · propose d'installer le cron quotidien (launchd).
# Ne committe RIEN, n'envoie AUCUN ordre. Les clés API restent à VOUS de les poser.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PY="$(command -v python3 || command -v python)"
PROFILE="${HOME}/.zshrc"; [ -n "${BASH_VERSION:-}" ] && [ -f "${HOME}/.bashrc" ] && PROFILE="${HOME}/.bashrc"

echo "▶ 1/4 — environnement virtuel + dépendances"
[ -d .venv ] || "$PY" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install -q --upgrade pip
python -m pip install -q -e ".[data,quant,ml,api]" 2>/dev/null || \
  python -m pip install -q numpy pandas pyyaml fastapi "uvicorn[standard]" scikit-learn yfinance

echo "▶ 2/4 — détection de la base de prix réelle (YAHOO.db)"
DB=""
for c in "$QUANT_PRICE_DB" "$HOME/Desktop/YAHOO.db" "$HOME/Bureau/YAHOO.db" "$ROOT/data/YAHOO.db" "$HOME/YAHOO.db"; do
  [ -n "$c" ] && [ -f "$c" ] && { DB="$c"; break; }
done
if [ -n "$DB" ]; then
  echo "  ✅ trouvée : $DB"
  if ! grep -q "QUANT_PRICE_DB=" "$PROFILE" 2>/dev/null; then
    echo "export QUANT_PRICE_DB=\"$DB\"" >> "$PROFILE"
    echo "  → ajouté à $PROFILE (rouvrez le terminal ou : source $PROFILE)"
  fi
  export QUANT_PRICE_DB="$DB"
else
  echo "  ⚠️  YAHOO.db introuvable → le terminal tournera en synthétique."
  echo "     Placez-la sur le Bureau ou faites : export QUANT_PRICE_DB=/chemin/vers/YAHOO.db"
fi

echo "▶ 3/4 — construction du terminal autonome"
python apps/web/preview/build_interactive.py

echo "▶ 4/4 — cron quotidien (optionnel)"
if [ "$(uname)" = "Darwin" ]; then
  PLIST="$HOME/Library/LaunchAgents/com.quant.daily.plist"
  read -r -p "  Installer la mise à jour quotidienne 22h30 (launchd) ? [y/N] " ans || ans="N"
  if [ "${ans:-N}" = "y" ] || [ "${ans:-N}" = "Y" ]; then
    cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.quant.daily</string>
  <key>ProgramArguments</key><array><string>$ROOT/scripts/cron_daily.sh</string></array>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>22</integer><key>Minute</key><integer>30</integer></dict>
  <key>StandardOutPath</key><string>/tmp/quant_daily.log</string>
  <key>StandardErrorPath</key><string>/tmp/quant_daily.err</string>
</dict></plist>
PLISTEOF
    launchctl unload "$PLIST" 2>/dev/null || true
    launchctl load "$PLIST" && echo "  ✅ cron installé (logs : /tmp/quant_daily.log)"
  else
    echo "  (ignoré — vous pourrez lancer 'make cron' manuellement)"
  fi
else
  echo "  Linux : ajoutez à 'crontab -e' →  30 22 * * 1-5 $ROOT/scripts/cron_daily.sh >> /tmp/quant_daily.log 2>&1"
fi

echo ""
echo "✅ Terminé."
echo "   • Terminal autonome : ouvrez apps/web/preview/interactive.html"
echo "   • Front complet      : make api   (puis  cd apps/web && npm install && npm run dev)"
echo "   • Fondamentaux réels : export FMP_API_KEY=\"votre_clé\"  (free tier)"
