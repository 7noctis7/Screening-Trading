#!/usr/bin/env bash
# Active la mise à jour quotidienne automatique (prix réels + terminal) en UNE commande.
#   macOS  → launchd (LaunchAgent, 22h30 en semaine)
#   Linux  → crontab (idem)
# Désinstaller : bash scripts/install_cron.sh --uninstall
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CRON_SH="$ROOT/scripts/cron_daily.sh"
chmod +x "$CRON_SH" 2>/dev/null || true
LABEL="com.quant.daily"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
ACTION="${1:-install}"

is_macos() { [ "$(uname -s)" = "Darwin" ]; }

if is_macos; then
  if [ "$ACTION" = "--uninstall" ]; then
    launchctl unload "$PLIST" 2>/dev/null || true; rm -f "$PLIST"
    echo "✅ launchd désinstallé ($LABEL)."; exit 0
  fi
  mkdir -p "$HOME/Library/LaunchAgents"
  cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array>
    <string>/bin/bash</string><string>$CRON_SH</string>
  </array>
  <key>StartCalendarInterval</key><array>
    <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>22</integer><key>Minute</key><integer>30</integer></dict>
    <dict><key>Weekday</key><integer>2</integer><key>Hour</key><integer>22</integer><key>Minute</key><integer>30</integer></dict>
    <dict><key>Weekday</key><integer>3</integer><key>Hour</key><integer>22</integer><key>Minute</key><integer>30</integer></dict>
    <dict><key>Weekday</key><integer>4</integer><key>Hour</key><integer>22</integer><key>Minute</key><integer>30</integer></dict>
    <dict><key>Weekday</key><integer>5</integer><key>Hour</key><integer>22</integer><key>Minute</key><integer>30</integer></dict>
  </array>
  <key>StandardOutPath</key><string>/tmp/quant_daily.log</string>
  <key>StandardErrorPath</key><string>/tmp/quant_daily.log</string>
  <key>RunAtLoad</key><false/>
</dict></plist>
PLISTEOF
  launchctl unload "$PLIST" 2>/dev/null || true
  launchctl load "$PLIST"
  echo "✅ launchd installé : maj quotidienne 22h30 (lun-ven). Logs : /tmp/quant_daily.log"
  echo "   Test immédiat : launchctl start $LABEL"
else
  LINE="30 22 * * 1-5 $CRON_SH >> /tmp/quant_daily.log 2>&1"
  if [ "$ACTION" = "--uninstall" ]; then
    crontab -l 2>/dev/null | grep -vF "$CRON_SH" | crontab - || true
    echo "✅ crontab désinstallé."; exit 0
  fi
  ( crontab -l 2>/dev/null | grep -vF "$CRON_SH"; echo "$LINE" ) | crontab -
  echo "✅ crontab installé : maj quotidienne 22h30 (lun-ven). Logs : /tmp/quant_daily.log"
fi
