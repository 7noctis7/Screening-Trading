#!/usr/bin/env bash
# Point d'entrée de `quant-web.service` — front Next en mode PRODUCTION.
#
# Pourquoi `build` + `start` et non `next dev` : un serveur de développement garde un
# compilateur en mémoire, recompile à chaud et supporte mal d'être un service au long
# cours. Surtout, c'est SON enfant `next-server` qui survivait à chaque déconnexion SSH
# en gardant le port 3000 (07/09). Sous systemd, le processus a un parent qui sait
# l'arrêter, et le mode production est plus léger et plus stable.
#
# Contrepartie assumée : après un `make sync`, il faut `sudo systemctl restart quant-web`
# pour reconstruire. Un rebuild coûte 1 à 2 minutes ; d'où TimeoutStartSec généreux.
set -eu
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
source scripts/env_quant.sh
cd apps/web

# `next.config` bascule en `output:"export"` dès que STATIC_EXPORT=1 — et un build exporté
# n'est PAS servable par `next start` (il n'y a plus de serveur). Comme systemd charge le
# `.env` du dépôt, une variable qui y traînerait casserait le service sans rapport visible
# avec sa cause. On neutralise ici, explicitement : ce service sert du rendu serveur.
unset STATIC_EXPORT NEXT_PUBLIC_STATIC NEXT_PUBLIC_BASE_PATH

# Même garde qu'en local : un cache `.next` produit par un autre commit resert l'ANCIEN
# rendu sans que rien ne le signale. On tamponne le commit hors de `.next`.
EMPREINTE=".quant-build-commit"
TETE="$(git rev-parse HEAD 2>/dev/null || echo inconnu)"
if [ "$(cat "$EMPREINTE" 2>/dev/null)" != "$TETE" ] || [ ! -d ".next" ]; then
  npm install >/dev/null 2>&1 || true
  npm run build
  echo "$TETE" >"$EMPREINTE"
fi

# -H 127.0.0.1 : le site affiche des positions réelles et n'a pas d'authentification.
# Accès par tunnel SSH uniquement. Ne jamais exposer sur 0.0.0.0.
exec npx next start -H "$QUANT_BIND_HOST" -p "$QUANT_WEB_PORT"
