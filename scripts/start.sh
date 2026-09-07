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
source scripts/env_quant.sh      # venv + variables QUANT_* — partagé avec les services systemd

# ON MET À JOUR LA BRANCHE OÙ L'ON EST — pas `main`. Le forçage sur `main` visait un vrai
# danger (une branche de travail restée en arrière, et `make start` qui ramenait du code vieux
# de quatre PR sans rien dire), mais il en créait un pire, mesuré le 04/09 : `make sync` alignait
# la branche de dev sur ses derniers commits, puis `make start` la RÉÉCRASAIT sur `main` deux
# secondes plus tard. Les correctifs livrés ne tournaient jamais, et rien ne le signalait — on
# cherchait un bug de cache dans du code qui n'était même pas chargé. Le Makefile de `main`
# étant plus ancien, `make sync` disparaissait ensuite, ce qui rendait la sortie impossible.
#
# Le danger d'origine est traité par un AVERTISSEMENT, pas par un écrasement : on dit de combien
# de commits la branche est en retard sur `main` et comment se réaligner. Informer laisse le
# choix ; écraser le retire.
BRANCH="${QUANT_BRANCH:-$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)}"
# HEAD détaché (ou dépôt illisible) : aucune branche à suivre, on retombe sur `main`.
[ "$BRANCH" = "HEAD" ] && BRANCH="main"
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
  # Le garde-fou qui remplace l'écrasement : on DIT le retard sur `main` au lieu de le corriger
  # d'autorité. Silence = la branche contient tout ce que `main` contient.
  if [ "$BRANCH" != "main" ] && git fetch origin main >/dev/null 2>&1; then
    _retard="$(git rev-list --count HEAD..origin/main 2>/dev/null || echo 0)"
    if [ "${_retard:-0}" -gt 0 ]; then
      echo "  ⚠ $BRANCH est en retard de $_retard commit(s) sur main."
      echo "    Pour vous réaligner : git fetch origin main && git reset --hard origin/main"
    fi
  fi
fi

echo "→ Arrêt des anciens process (API/front)…"
bash scripts/stop_services.sh

# Next bascule SILENCIEUSEMENT sur 3001 si 3000 est déjà pris. On le SIGNALE (l'API autorise
# désormais aussi l'origine 3001, donc ce n'est plus fatal — mais le tunnel doit suivre).
# NE PAS DEMANDER « y a-t-il un listener ? » MAIS « puis-je réserver ce port ? ».
# Mesuré le 07/09 : `ss -ltn` ET `sudo ss -ltnp` rendaient le port 3000 VIDE, pendant que Next
# refusait de s'y lier et basculait sur 3001 — que le CORS de l'API rejette, donc une page qui
# s'affiche sans jamais charger de données. `ss -l` ne liste que l'état LISTEN : il ne voit ni
# les sockets résiduelles d'un process tué, ni un détenteur qu'il n'a pas le droit d'afficher.
# Le seul test fiable est celui que Next fera lui-même : tenter le bind, avec SO_REUSEADDR
# comme Node. On réessaie, car l'occupation est souvent transitoire après un kill.
_port_reservable() {
  python3 - "$1" <<'PYEOF' 2>/dev/null
import socket, sys
# RÉPLIQUER NODE EXACTEMENT, pas approximer. Un `server.listen(port)` de Node se lie à
# `::` en DOUBLE PILE (IPV6_V6ONLY=0). Tester `0.0.0.0` ne teste donc pas la même chose :
# un détenteur lié à `::` en IPv6-only laisse l'IPv4 libre, mon test réussissait et Next
# échouait juste après — la garde restait muette sur le cas exact qu'elle devait attraper
# (07/09, VPS avec IPv6 actif). Repli sur IPv4 là où AF_INET6 n'existe pas (conteneurs).
port = int(sys.argv[1])
try:
    s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
    hote = "::"
except OSError:
    s, hote = socket.socket(), "0.0.0.0"
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    s.bind((hote, port))
except OSError:
    sys.exit(1)
finally:
    s.close()
PYEOF
}

for _essai in $(seq 1 30); do
  if _port_reservable 3000; then break; fi
  [ "$_essai" = "1" ] && echo "  Port 3000 encore occupé, attente de sa libération (30 s max)…"
  sleep 1
done
if ! _port_reservable 3000; then
  echo "✗ Le port 3000 reste impossible à réserver après 30 s."
  echo "  Next basculerait sur 3001, que le CORS de l'API refuse : la page s'afficherait mais"
  echo "  AUCUNE donnée ne se chargerait, sans autre symptôme qu'une panne réseau anonyme."
  echo "  État COMPLET des sockets sur ce port (tous états, pas seulement LISTEN) :"
  (ss -tanp "sport = :3000" 2>/dev/null || lsof -i:3000 -P -n 2>/dev/null) | sed 's/^/    /'
  echo "  Si rien n'apparaît ci-dessus, le détenteur appartient à un autre compte :"
  echo "      sudo ss -tanp 'sport = :3000'"
  exit 1
fi

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

# CONTRÔLE TARDIF, juste avant `next dev`. Le 07/09, la garde placée après l'arrêt des process
# voyait le port LIBRE (bind réussi) et Next le trouvait OCCUPÉ quelques secondes plus tard :
# le détenteur apparaît donc APRÈS elle, pendant le démarrage de l'API, la purge du cache ou
# `npm install`. Vérifier au plus près du lancement est le seul moment où la mesure peut
# désigner le vrai coupable.
if ! _port_reservable 3000; then
  echo "⚠ Port 3000 repris ENTRE la vérification initiale et le lancement du site."
  _diagnostic_port 3000
  echo "  Le site va démarrer sur 3001. L'API l'autorise, mais votre tunnel doit suivre :"
  echo "      ssh -L 3001:localhost:3001 -L 8000:localhost:8000 ubuntu@<vps>"
fi

echo "  Ouvre http://localhost:3000  (laisse ~1-3 min au 1er build de l'API)"
npm run dev
