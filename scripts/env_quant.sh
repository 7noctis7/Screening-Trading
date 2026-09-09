#!/usr/bin/env bash
# Environnement commun à `make start` ET aux services systemd. UNE seule définition :
# deux copies auraient divergé sans que rien ne le signale — c'est la famille de défauts
# qui a coûté la journée du 07/09 (clé `hrp` d'un côté, `black_litterman` de l'autre).
# À SOURCER, jamais à exécuter. Chaque valeur reste surchargeable par l'appelant.
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
# QUANT_CORE_SPEC / QUANT_DD_TARGET : respectés s'ils sont définis (sinon défaut code).

# L'API et le front n'écoutent QUE sur la boucle locale. Le dépôt est public et la page
# affiche des positions réelles ; l'API n'a aucune authentification. On y accède par un
# tunnel SSH, jamais en exposant le port. Ne PAS mettre 0.0.0.0 ici.
export QUANT_BIND_HOST="${QUANT_BIND_HOST:-127.0.0.1}"
export QUANT_API_PORT="${QUANT_API_PORT:-8000}"
export QUANT_WEB_PORT="${QUANT_WEB_PORT:-3000}"
