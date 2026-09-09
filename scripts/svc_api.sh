#!/usr/bin/env bash
# Point d'entrée de `quant-api.service`. Existe pour que le service et `make start`
# partagent l'environnement (scripts/env_quant.sh) au lieu de le redéclarer chacun.
set -eu
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
source scripts/env_quant.sh
# --host 127.0.0.1 : l'API n'a AUCUNE authentification et le VPS est sur l'Internet public.
# On y accède par tunnel SSH. Ne jamais remplacer par 0.0.0.0.
exec python -m uvicorn apps.api.main:app \
  --host "$QUANT_BIND_HOST" --port "$QUANT_API_PORT"
