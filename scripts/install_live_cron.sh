#!/usr/bin/env bash
# Active le REBALANCEMENT PAPER quotidien automatique en UNE commande.
#   macOS → launchd (LaunchAgent, lun-ven, heure LOCALE)
#   Linux → crontab (idem)
# Désinstaller : bash scripts/install_live_cron.sh --uninstall
#
# HEURE — configurable, et le défaut n'est pas anodin :
#   QUANT_LIVE_HOUR=20 QUANT_LIVE_MIN=5 make live-cron-install
#
# La séance NYSE va de 15h30 à 22h00 heure de Paris. Le défaut 16h05 vise juste après
# l'ouverture ; 20h05 vise les deux dernières heures, ce qui convient mieux à un
# rebalancement QUOTIDIEN (plus de liquidité, moins de bruit intraday) et surtout à une
# machine qui n'est allumée que le soir. Hors séance, `run_live` ne passe rien en force :
# il REPORTE les ordres actions et le dit (le crypto, lui, tourne 24/7).
#
# Éviter 21h30-22h00 : entre le changement d'heure européen (dernier dimanche d'octobre)
# et américain (premier dimanche de novembre), l'écart Paris↔New York passe à 5 h une
# semaine par an — la clôture tombe alors à 21h00 heure de Paris.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CRON_SH="$ROOT/scripts/cron_live.sh"
chmod +x "$CRON_SH" 2>/dev/null || true
LABEL="com.quant.live"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
HOUR="${QUANT_LIVE_HOUR:-16}"
MIN="${QUANT_LIVE_MIN:-5}"
ACTION="${1:-install}"

is_macos() { [ "$(uname -s)" = "Darwin" ]; }

# Log PERSISTANT au reboot : sur macOS `/tmp` est purgé au redémarrage → on écrit dans
# ~/Library/Logs (emplacement standard, survit au reboot). Sur Linux, /tmp convient.
if is_macos; then
  LOG="$HOME/Library/Logs/quant_live.log"; mkdir -p "$HOME/Library/Logs"
else
  LOG="/tmp/quant_live.log"
fi

if is_macos; then
  if [ "$ACTION" = "--uninstall" ]; then
    launchctl unload "$PLIST" 2>/dev/null || true; rm -f "$PLIST"
    echo "✅ launchd désinstallé ($LABEL) — plus de rebalancement auto."; exit 0
  fi
  mkdir -p "$HOME/Library/LaunchAgents"
  {
    echo '<?xml version="1.0" encoding="UTF-8"?>'
    echo '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">'
    echo '<plist version="1.0"><dict>'
    echo "  <key>Label</key><string>$LABEL</string>"
    echo '  <key>ProgramArguments</key><array>'
    echo "    <string>/bin/bash</string><string>$CRON_SH</string>"
    echo '  </array>'
    echo '  <key>StartCalendarInterval</key><array>'
    for d in 1 2 3 4 5; do
      echo "    <dict><key>Weekday</key><integer>$d</integer><key>Hour</key><integer>$HOUR</integer><key>Minute</key><integer>$MIN</integer></dict>"
    done
    echo '  </array>'
    echo "  <key>StandardOutPath</key><string>$LOG</string>"
    echo "  <key>StandardErrorPath</key><string>$LOG</string>"
    echo '  <key>RunAtLoad</key><false/>'
    echo '</dict></plist>'
  } > "$PLIST"
  launchctl unload "$PLIST" 2>/dev/null || true
  launchctl load "$PLIST"
  echo "✅ launchd activé : rebalancement PAPER lun-ven $(printf "%02dh%02d" "$HOUR" "$MIN") → $LOG"
  echo "   (Alpaca paper forcé ; crypto réel neutralisé. Désactiver : make live-cron-uninstall)"
else
  LINE="$MIN $HOUR * * 1-5 $CRON_SH >> $LOG 2>&1"
  if [ "$ACTION" = "--uninstall" ]; then
    (crontab -l 2>/dev/null | grep -vF "$CRON_SH") | crontab - || true
    echo "✅ crontab nettoyé — plus de rebalancement auto."; exit 0
  fi
  (crontab -l 2>/dev/null | grep -vF "$CRON_SH"; echo "$LINE") | crontab -
  echo "✅ crontab activé : rebalancement PAPER lun-ven $(printf "%02dh%02d" "$HOUR" "$MIN") → $LOG"
fi
