#!/usr/bin/env bash
# « Quelque chose répond sur le port 3000 » N'EST PAS « le service sert le code courant ».
#
# Le 07/09, `make up` annonçait « front prêt » pendant que le navigateur parlait à un
# `next dev` orphelin d'une session SSH morte : la page fonctionnait, affichait du code
# vieux de quinze commits, et aucune commande ne le signalait. C'est la troisième fois de
# la journée qu'un outil dit « fait » sans que ce soit vrai — d'où cette vérification, qui
# ne demande pas « ça répond ? » mais « QUI répond, et avec QUEL build ? ».
set -u
cd "$(dirname "$0")/.."
PORT="${QUANT_WEB_PORT:-3000}"
statut=0
# `--unite` : ne contrôle QUE la version de l'unité. Appelé au DÉBUT de `make up`, il évite
# de faire recompiler deux minutes pour annoncer ensuite qu'il fallait d'abord réinstaller.
# Une vérification tardive coûte le temps de tout ce qu'elle laisse faire avant de refuser.
SEULEMENT_UNITE=0
[ "${1:-}" = "--unite" ] && SEULEMENT_UNITE=1

if [ "$SEULEMENT_UNITE" = "0" ]; then
# 1. QUI tient le port : le PID doit appartenir au service, pas à un processus orphelin.
if command -v systemctl >/dev/null 2>&1 \
   && systemctl is-active --quiet quant-web.service 2>/dev/null; then
  attendu="$(systemctl show quant-web.service -p MainPID --value 2>/dev/null)"
  tenant="$(ss -H -ltnp "sport = :$PORT" 2>/dev/null | grep -oE 'pid=[0-9]+' | head -1 | cut -d= -f2)"
  if [ -n "$tenant" ] && [ -n "$attendu" ] && [ "$attendu" != "0" ]; then
    # Le serveur Next est un ENFANT du script du service : on remonte la filiation.
    racine="$tenant"
    for _ in 1 2 3 4 5; do
      [ "$racine" = "$attendu" ] && break
      parent="$(ps -o ppid= -p "$racine" 2>/dev/null | tr -d ' ')"
      [ -z "$parent" ] || [ "$parent" = "1" ] && break
      racine="$parent"
    done
    if [ "$racine" != "$attendu" ]; then
      echo "✗ Le port $PORT est tenu par le PID $tenant, ÉTRANGER au service quant-web (PID $attendu)."
      echo "  Votre navigateur parle à un processus orphelin qui sert du code périmé."
      echo "  Le tuer puis relancer :   sudo kill -9 $tenant && make up"
      statut=1
    fi
  fi
fi

fi

# 2. QUELLE UNITÉ : le fichier systemd installé doit correspondre au gabarit du dépôt.
attendue="$(grep -oP '^VERSION_UNITE=\K[0-9]+' scripts/install_services.sh 2>/dev/null || echo '')"
installee="$(grep -oP '^# quant-unit-version: \K[0-9]+' /etc/systemd/system/quant-web.service 2>/dev/null || echo '')"
if [ -n "$attendue" ] && [ "$installee" != "$attendue" ]; then
  echo "✗ L'unité systemd installée est en version « ${installee:-inconnue} », le dépôt attend « $attendue »."
  echo "  Des correctifs d'unité (arrêt des enfants, chemin d'exécution) ne sont donc PAS appliqués."
  echo "  Réinstaller :   make services"
  statut=1
fi

if [ "$SEULEMENT_UNITE" = "1" ]; then
  exit "$statut"
fi

# 3. QUEL build : le tampon posé au moment du build doit valoir la tête courante.
tete="$(git rev-parse --short HEAD 2>/dev/null || echo '?')"
bati="$(cut -c1-7 apps/web/.quant-build-commit 2>/dev/null || echo '?')"
if [ "$tete" != "$bati" ]; then
  echo "✗ Le front servi a été construit sur $bati, or la tête est $tete."
  echo "  Relancer :   sudo systemctl restart quant-web"
  statut=1
fi

if [ "$statut" -eq 0 ]; then
  echo "✓ front prêt   → http://localhost:$PORT   (build $bati, servi par quant-web)"
  printf "✓ API %s\n" "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/health)"
fi
exit "$statut"
