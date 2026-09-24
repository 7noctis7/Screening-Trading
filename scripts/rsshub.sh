#!/usr/bin/env bash
# RSSHUB AUTO-HÉBERGÉ — la voie GRATUITE et DURABLE pour lire les comptes X.
#
#   make rsshub                 # démarre (ou met à jour) le conteneur
#   make rsshub ARGS=statut     # répond-il, et avec quel compte ?
#   make rsshub ARGS=arret
#
# POURQUOI CETTE VOIE. L'API X gratuite ne sait pas LIRE (la lecture est payante,
# « Pay-Per-Use »). Les miroirs publics de type Nitter meurent en permanence. RSSHub est
# un projet open-source très suivi qui suit les changements de X à notre place ; on
# l'héberge SOI-MÊME, donc il ne dépend du bon vouloir de personne — sauf de X.
# Vérifié sur ses sources (lib/routes/twitter, 09/2026) : la route utilisateur est
# `/twitter/user/:id`, elle n'exige PAS de navigateur, et l'authentification
# recommandée est `TWITTER_AUTH_TOKEN` — le cookie `auth_token` d'une session x.com.
# L'ancienne voie identifiant/mot de passe ne marche plus depuis octobre 2025.
#
# LE COOKIE EST UN SECRET, ET PAS N'IMPORTE LEQUEL : c'est une SESSION COMPLÈTE sur le
# compte X qui l'a émis. D'où les deux gardes ci-dessous, qui ne sont pas négociables :
#   1. il vit HORS du dépôt (public), dans un fichier lisible par son seul propriétaire ;
#      le script REFUSE de démarrer si ce fichier est lisible par d'autres ;
#   2. le port n'écoute QUE sur la boucle locale. Le `docker-compose.yml` officiel publie
#      `1200:1200`, c'est-à-dire sur TOUTES les interfaces — et Docker contourne ufw.
#      Sur le VPS, ce serait offrir à Internet un relais anonyme vers le compte X.
#
# UTILISER UN COMPTE SECONDAIRE, JAMAIS LE PRINCIPAL. Les conditions d'X interdisent la
# lecture automatisée ; le compte dont le cookie sert ici peut être limité ou suspendu.
set -euo pipefail

NOM="quant-rsshub"
IMAGE="diygod/rsshub"
HOTE="127.0.0.1"
PORT="${QUANT_RSSHUB_PORT:-1200}"
SECRET="${QUANT_RSSHUB_ENV:-$HOME/.config/quant/rsshub.env}"

_secret_sain() {
  if [ ! -f "$SECRET" ]; then
    echo "✗ $SECRET absent. Le créer (compte X SECONDAIRE) :"
    echo "    mkdir -p \"$(dirname "$SECRET")\""
    echo "    printf 'TWITTER_AUTH_TOKEN=%s\\n' '<cookie auth_token>' > \"$SECRET\""
    echo "    chmod 600 \"$SECRET\""
    return 1
  fi
  # `stat -c` (GNU) puis `stat -f` (BSD/macOS) : le script tourne sur les deux.
  local droits
  droits="$(stat -c '%a' "$SECRET" 2>/dev/null || stat -f '%Lp' "$SECRET")"
  if [ "${droits: -2}" != "00" ]; then
    echo "✗ $SECRET est lisible par d'autres (droits $droits). Refus de démarrer."
    echo "    chmod 600 \"$SECRET\""
    return 1
  fi
  grep -q '^TWITTER_AUTH_TOKEN=.\+' "$SECRET" \
    || { echo "✗ TWITTER_AUTH_TOKEN vide dans $SECRET."; return 1; }
}

_demarrer() {
  command -v docker >/dev/null || { echo "✗ docker absent : sudo apt install docker.io"; exit 1; }
  _secret_sain || exit 1
  docker pull --quiet "$IMAGE" >/dev/null   # X change souvent : la route suit l'image
  docker rm -f "$NOM" >/dev/null 2>&1 || true
  docker run -d --name "$NOM" --restart unless-stopped \
    -p "$HOTE:$PORT:1200" --env-file "$SECRET" -e NODE_ENV=production \
    "$IMAGE" >/dev/null
  echo "✓ RSSHub sur http://$HOTE:$PORT (boucle locale uniquement)."
  echo "  Vérifier : make rsshub ARGS=statut"
}

_statut() {
  local url="http://$HOTE:$PORT"
  if ! curl -fsS --max-time 5 "$url/healthz" >/dev/null 2>&1; then
    echo "✗ RSSHub ne répond pas sur $url — make rsshub pour le démarrer."; exit 1
  fi
  echo "✓ RSSHub répond sur $url."
  echo "  Mesurer ce qu'il rend pour les comptes suivis :"
  echo "    make x-miroirs ARGS='--miroirs $url/twitter/user/{compte}/includeRts=0'"
}

case "${1:-demarrer}" in
  demarrer|"") _demarrer ;;
  statut) _statut ;;
  arret) docker rm -f "$NOM" >/dev/null 2>&1 && echo "✓ arrêté." || echo "(déjà arrêté)" ;;
  *) echo "usage : $0 [demarrer|statut|arret]"; exit 2 ;;
esac
