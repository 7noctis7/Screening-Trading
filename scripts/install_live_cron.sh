#!/usr/bin/env bash
# Active le REBALANCEMENT PAPER quotidien automatique en UNE commande.
#   macOS → launchd (LaunchAgent, lun-ven, heure LOCALE)
#   Linux → crontab (idem)
# Désinstaller : bash scripts/install_live_cron.sh --uninstall
#
# QUAND — par défaut, une heure avant la clôture NYSE, TOUTE L'ANNÉE, sans réglage.
#   QUANT_LIVE_AVANT_CLOTURE=30 make live-cron-install    # viser 30 min avant
#   QUANT_LIVE_HOUR=20 make live-cron-install             # revenir à une heure fixe
#
# Le planificateur se réveille chaque heure ouvrée et `scripts/fenetre_execution.py`
# décide, dans l'heure du MARCHÉ, s'il faut agir : une seule des vingt-quatre tentatives
# tombe dans la fenêtre, et les autres sortent en silence.
#
# POURQUOI PAS UNE HEURE FIXE. La clôture de 16 h à New York tombe à 20 h UTC l'été et à
# 21 h UTC l'hiver. Les bascules américaine (1er dim. de novembre) et européenne (dernier
# dim. d'octobre) ne tombent pas le même week-end : pendant une semaine par an, l'écart
# Paris↔New York passe à 5 h. Une heure de cron gelée dérive donc au moins deux fois par
# an, et il faut y repenser à chaque fois. Le calendrier du projet connaît déjà ces
# règles et les fériés NYSE : autant les lui demander plutôt que de les recopier ici.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CRON_SH="$ROOT/scripts/cron_live.sh"
chmod +x "$CRON_SH" 2>/dev/null || true
LABEL="com.quant.live"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
# HEURE FIXE = LEGACY. Par défaut on ne fixe PLUS d'heure : le planificateur se réveille
# toutes les heures et `scripts/fenetre_execution.py` décide, dans l'heure du MARCHÉ, s'il
# faut agir. C'est la seule façon de viser « une heure avant la clôture » sans rien
# retoucher : la clôture de 16 h à New York tombe à 20 h UTC l'été et 21 h l'hiver, les
# bascules américaine et européenne ne tombent pas le même dimanche, et la machine peut
# vivre dans n'importe quel fuseau. Une heure gelée dérive au moins deux fois par an.
# `QUANT_LIVE_HOUR=20` force encore une heure précise pour qui le souhaite.
HOUR="${QUANT_LIVE_HOUR:-}"
MIN="${QUANT_LIVE_MIN:-5}"
CIBLE="${QUANT_LIVE_AVANT_CLOTURE:-60}"
if [ -n "$HOUR" ]; then
  QUAND="tous les jours ouvrés à $(printf "%02dh%02d" "$HOUR" "$MIN") (heure fixe)"
  CRON_HEURE="$HOUR"
  PLIST_HEURE="    <key>Hour</key><integer>$HOUR</integer>"
else
  QUAND="chaque heure ouvrée, agit ${CIBLE} min avant la clôture NYSE"
  CRON_HEURE="*"
  PLIST_HEURE=""
fi
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
      echo "    <dict><key>Weekday</key><integer>$d</integer>$PLIST_HEURE<key>Minute</key><integer>$MIN</integer></dict>"
    done
    echo '  </array>'
    echo "  <key>StandardOutPath</key><string>$LOG</string>"
    echo "  <key>StandardErrorPath</key><string>$LOG</string>"
    echo '  <key>RunAtLoad</key><false/>'
    echo '</dict></plist>'
  } > "$PLIST"
  launchctl unload "$PLIST" 2>/dev/null || true
  launchctl load "$PLIST"
  echo "✅ launchd activé : rebalancement PAPER lun-ven — $QUAND → $LOG"
  echo "   (Alpaca paper forcé ; crypto réel neutralisé. Désactiver : make live-cron-uninstall)"
else
  LINE="$MIN $CRON_HEURE * * 1-5 $CRON_SH >> $LOG 2>&1"
  if [ "$ACTION" = "--uninstall" ]; then
    { crontab -l 2>/dev/null | grep -vF "$CRON_SH" || true; } | crontab - || true
    echo "✅ crontab nettoyé — plus de rebalancement auto."; exit 0
  fi
  # `|| true` OBLIGATOIRE, et c'est tout sauf cosmétique. Sans crontab existant,
  # `crontab -l` échoue et `grep` ne sélectionne aucune ligne : il sort en 1. Avec
  # `set -euo pipefail`, le sous-shell meurt AVANT le `echo "$LINE"`, la nouvelle ligne
  # n'est jamais écrite, et le script rend 1 sans un mot. Autrement dit : l'installateur
  # ne fonctionnait QUE sur une machine ayant déjà un crontab — jamais sur celle qui en
  # a besoin. Constaté sur le VPS le 10/09 : « make: *** [live-cron-install] Error 1 »,
  # aucun message, et pas une ligne installée.
  { crontab -l 2>/dev/null | grep -vF "$CRON_SH" || true; echo "$LINE"; } | crontab -
  # On VÉRIFIE au lieu d'annoncer. Un installateur qui dit « activé » sans relire ce
  # qu'il a écrit est exactement ce qui a laissé ce défaut invisible.
  if crontab -l 2>/dev/null | grep -qF "$CRON_SH"; then
    echo "✅ crontab activé : rebalancement PAPER lun-ven — $QUAND → $LOG"
    echo "   vérifié : $(crontab -l | grep -F "$CRON_SH")"
  else
    echo "❌ la ligne n'est PAS dans le crontab après écriture — rien n'est planifié." >&2
    echo "   Vérifier que \`crontab\` est installé et utilisable par $(whoami)." >&2
    exit 1
  fi
fi
