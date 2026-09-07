#!/usr/bin/env bash
# Installe l'API et le front comme SERVICES systemd, pour qu'ils survivent aux
# déconnexions SSH, redémarrent seuls après un plantage et s'arrêtent proprement.
#
# LE PROBLÈME QUE ÇA RÈGLE (07/09) : `next dev` tournait au premier plan d'une session
# SSH. À la déconnexion, le shell recevait SIGHUP, `npm` mourait, mais l'enfant
# `next-server` survivait ORPHELIN en gardant le port 3000. Next basculait alors sur
# 3001, dont l'origine sortait de la liste CORS, et toutes les requêtes étaient refusées
# avant d'être émises — symptôme final : « TypeError: Load failed », qui accusait la
# donnée pour un port mal libéré. Un orphelin de plus à chaque cycle de connexion.
# Sous systemd, le processus a un parent qui sait l'arrêter : la boucle ne peut plus naître.
#
#   sudo bash scripts/install_services.sh
set -euo pipefail

RACINE="$(cd "$(dirname "$0")/.." && pwd)"
UTILISATEUR="${SUDO_USER:-$(id -un)}"
GROUPE="$(id -gn "$UTILISATEUR")"
FOYER="$(getent passwd "$UTILISATEUR" | cut -d: -f6)"

if [ "$(id -u)" -ne 0 ]; then
  echo "✗ À lancer avec sudo : sudo bash scripts/install_services.sh" >&2
  exit 1
fi
if [ "$UTILISATEUR" = "root" ]; then
  echo "✗ Refus d'installer les services sous root : ils doivent tourner sous le compte" >&2
  echo "  qui possède le dépôt et le venv. Lancez 'sudo bash …' depuis ce compte." >&2
  exit 1
fi

mkdir -p "$RACINE/logs"
chown "$UTILISATEUR:$GROUPE" "$RACINE/logs"

_unite() {   # $1 = nom, $2 = description, $3 = script, $4 = délai de démarrage
  cat >"/etc/systemd/system/$1.service" <<UNIT
[Unit]
Description=$2
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$UTILISATEUR
Group=$GROUPE
WorkingDirectory=$RACINE
Environment=HOME=$FOYER
# Le .env porte les clés courtier : facultatif (le préfixe '-'), jamais versionné.
EnvironmentFile=-$RACINE/.env
ExecStart=/usr/bin/env bash $3
Restart=always
RestartSec=5
TimeoutStartSec=$4
# Le build Next et l'ingestion sont gourmands : on ne les tue pas trop vite à l'arrêt.
TimeoutStopSec=30
# KillMode par DÉFAUT (control-group) : le signal d'arrêt va à TOUS les processus du
# service, pas au seul principal. `mixed` ne signalait que le principal, et tout enfant qui
# lui survivait gardait le port — c'est ainsi que des `next-server` orphelins se sont
# accumulés le 07/09 jusqu'à rendre le service impossible à démarrer. Ne pas remettre
# `mixed` sans avoir d'abord garanti qu'aucun enfant ne détient de ressource.
StandardOutput=append:$RACINE/logs/$1.log
StandardError=append:$RACINE/logs/$1.log

[Install]
WantedBy=multi-user.target
UNIT
  echo "  ✓ /etc/systemd/system/$1.service"
}

echo "→ Écriture des unités (utilisateur $UTILISATEUR, dépôt $RACINE)…"
_unite quant-api "Quant Terminal — API FastAPI (boucle locale uniquement)" \
       "$RACINE/scripts/svc_api.sh" 300
_unite quant-web "Quant Terminal — front Next.js (boucle locale uniquement)" \
       "$RACINE/scripts/svc_web.sh" 900

echo "→ Arrêt des processus lancés à la main (sinon ils garderaient les ports)…"
sudo -u "$UTILISATEUR" bash "$RACINE/scripts/stop_services.sh" || true

echo "→ Activation et démarrage…"
systemctl daemon-reload
systemctl enable --now quant-api.service quant-web.service

echo
echo "Installé. Le premier démarrage du front compile (1 à 2 min)."
echo "  état    : systemctl status quant-api quant-web"
echo "  logs    : journalctl -u quant-web -f     (ou logs/quant-web.log)"
echo "  relance : sudo systemctl restart quant-web     ← APRÈS chaque 'make sync'"
echo "  arrêt   : sudo systemctl stop quant-api quant-web"
