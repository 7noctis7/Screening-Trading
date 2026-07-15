#!/usr/bin/env bash
# Rebalancement PAPER quotidien automatique (sans intervention).
# Enchaîne : maj prix incrémentale → réconciliation du portefeuille modèle vers le
# broker (Alpaca = TOUJOURS paper ; cf. run_live.py:56). Idempotent, journalisé.
#
# Sécurité :
#   - Alpaca est forcé en paper → aucun ordre réel sur actions, quoi qu'il arrive.
#   - Bitmart (crypto) ne s'active que si des clés Bitmart sont présentes. Pour
#     INTERDIRE tout ordre crypto réel depuis ce cron, mettre QUANT_NO_CRYPTO_LIVE=1
#     (défaut ici) → on retire les clés Bitmart de l'environnement du run.
#   - Ne tourne QUE les jours de bourse US (lun-ven) ; sort proprement le week-end.
#
# Installation : make live-cron-install   ·   Désinstallation : make live-cron-uninstall
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# shellcheck disable=SC1091
[ -f .venv/bin/activate ] && source .venv/bin/activate
PY="${PYTHON:-python3}"

DOW="$(date +%u)"                                   # 1=lundi … 7=dimanche
if [ "$DOW" -ge 6 ]; then
  echo "[$(date '+%F %T')] week-end (marché fermé) → rien à faire."; exit 0
fi

# Garde-fou crypto : par défaut, on NEUTRALISE les clés Bitmart pour rester 100 % paper.
if [ "${QUANT_NO_CRYPTO_LIVE:-1}" = "1" ]; then
  unset BITMART_API_KEY BITMART_API_SECRET BITMART_API_MEMO 2>/dev/null || true
fi

echo "[$(date '+%F %T')] rebalancement paper — début"
$PY scripts/ingest_prices.py --daily || true       # prix frais (best-effort)
# FAIL-LOUD (audit 07/15) : l'échec de run_live est PROPAGÉ (l'ancien script sortait
# toujours 0 → launchd/Actions ne voyaient jamais une prod morte).
rc=0
$PY scripts/run_live.py --live --yes || rc=$?       # Alpaca paper ; Bitmart neutralisé
# Miroir Notion (audit 05/07) : best-effort, uniquement si NOTION_TOKEN présent dans .env.
$PY scripts/notion_sync.py >/dev/null 2>&1 || true
if [ "$rc" -ne 0 ]; then
  echo "[$(date '+%F %T')] rebalancement paper — ÉCHEC (code $rc)"; exit "$rc"
fi
echo "[$(date '+%F %T')] rebalancement paper — fin"
