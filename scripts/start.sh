#!/usr/bin/env bash
# Démarre Quant Terminal EN UNE COMMANDE : met à jour le code, tue les vieux process,
# lance l'API (en arrière-plan) puis le front. Plus besoin de 3 commandes/fenêtres.
#   make start        (ou : bash scripts/start.sh)
# Variables surchargeables : QUANT_BRANCH (défaut main), QUANT_PRICE_DB, QUANT_HISTORY_DAYS,
#   QUANT_NO_UPDATE=1 (saute le git reset),
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

# On se cale sur MAIN, pas sur une branche de travail. Une branche de travail n'est resynchronisée
# qu'après SON merge ; si une session en a utilisé une autre, celle-ci reste en arrière et le
# `git reset --hard` ci-dessous efface silencieusement tout ce qui a été livré entre-temps.
# C'est arrivé : `make start` ramenait un code vieux de quatre PR sans rien signaler.
# `main` porte toujours ce qui est mergé, quelle que soit la branche qui l'a produit.
BRANCH="${QUANT_BRANCH:-main}"
if [ "${QUANT_NO_UPDATE:-0}" != "1" ]; then
  echo "→ Mise à jour du code (origin/$BRANCH)…"
  _avant="$(git rev-parse --short HEAD 2>/dev/null || echo '?')"
  if git fetch origin "$BRANCH" >/dev/null 2>&1 && git reset --hard "origin/$BRANCH" >/dev/null 2>&1; then
    _apres="$(git rev-parse --short HEAD)"
    if [ "$_avant" = "$_apres" ]; then
      echo "  ✓ déjà à jour ($_apres)"
    else
      # On DIT ce qui a changé : un reset --hard silencieux est le meilleur moyen de tourner
      # pendant des jours sur du code qu'on croit à jour.
      echo "  ✓ $_avant → $_apres ($(git log --oneline "$_avant".."$_apres" 2>/dev/null | wc -l | tr -d ' ') commit(s))"
    fi
  else
    echo "  ⚠ maj ignorée (hors-ligne ?) — le code local reste sur $(git rev-parse --short HEAD 2>/dev/null || echo '?')"
  fi
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

# LE CACHE .next RESERT L'ANCIEN RENDU. Signalé le 03/09 : après un `make sync` qui
# ramenait `/sentiment` dans la barre, le menu « Marché » affichait toujours ses cinq
# anciennes entrées, et une étiquette macro corrigée restait dans sa version fausse. Le
# code était bon, le build ne l'était pas — et rien ne le disait, ce qui est le pire cas :
# on croit lire le résultat de son correctif, on lit celui d'avant.
#
# On tamponne le commit avec lequel le cache a été produit, HORS de `.next` (que Next
# régénère). S'il diffère de la tête courante, on purge : quelques secondes de rebuild
# contre une heure à chercher un bug déjà corrigé.
EMPREINTE=".quant-build-commit"
TETE="$(git rev-parse HEAD 2>/dev/null || echo inconnu)"
if [ "$(cat "$EMPREINTE" 2>/dev/null)" != "$TETE" ]; then
  echo "  Code modifié depuis le dernier build → purge du cache .next (rebuild ~30 s)"
  rm -rf .next
  echo "$TETE" >"$EMPREINTE"
fi

npm install >/dev/null 2>&1 || true
echo "  Ouvre http://localhost:3000  (laisse ~1-3 min au 1er build de l'API)"
npm run dev
