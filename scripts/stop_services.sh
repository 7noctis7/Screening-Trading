#!/usr/bin/env bash
# Arrêt des services locaux (API uvicorn + front Next). Utilisé par `make stop` ET par
# `scripts/start.sh` : une seule définition de ce qu'on tue, donc aucune divergence
# possible entre les deux chemins.
set -u
cd "$(dirname "$0")/.."

# `pkill -f "uvicorn apps.api.main"` SE TUAIT LUI-MÊME depuis une ligne de Makefile :
# make exécute la recette via `/bin/sh -c '…'` dont la ligne de commande CONTIENT le
# motif. pkill terminait donc ce shell, make affichait « [Makefile:43: stop] Terminated »
# et les nettoyages de ports qui suivaient n'étaient JAMAIS exécutés (mesuré le 07/09).
# Les crochets cassent l'auto-correspondance sans changer la cible.
pkill -f "uvicorn apps[.]api[.]main" 2>/dev/null || true

# Détenteurs d'un port. NE PAS dépendre du seul `lsof` : le 07/09, `make stop` annonçait
# « arrêté » pendant qu'un `next-server` tenait le port 3000 depuis des heures — il a
# survécu à tous les redémarrages, forçant Next sur 3001 et cassant le CORS. `ss` est
# présent par défaut sur Ubuntu et voit la socket ; `lsof` reste en repli.
_pids_sur_port() {
  { command -v ss >/dev/null 2>&1 \
      && ss -H -ltnp "sport = :$1" 2>/dev/null | grep -oE 'pid=[0-9]+' | cut -d= -f2
    lsof -ti:"$1" 2>/dev/null
  } | sort -u
}

for port in 8000 3000; do
  for pid in $(_pids_sur_port "$port"); do
    nom="$(ps -p "$pid" -o comm= 2>/dev/null | tr -d ' ')"
    case "$nom" in
      # `kill -9 $(lsof -ti:PORT)` est aveugle : il a tué un tunnel `ssh -L` ouvert sur
      # cette machine, et avec lui la session qui lançait `make start` (07/09). Un tunnel
      # n'est pas un service à redémarrer : on le signale, on ne le tue pas.
      ssh|sshd)
        echo "  ⚠ port $port tenu par $nom (PID $pid) — NON tué : c'est un tunnel, pas un service."
        echo "    Fermez-le depuis la machine qui l'a ouvert, ou changez de port."
        ;;
      *) kill -9 "$pid" 2>/dev/null || true ;;
    esac
  done
done

# Filet de sécurité par NOM : un `next-server` peut survivre au `next dev` qui l'a lancé.
# Mais un `pkill -f` nu est trop grossier — il frappe TOUT ce dont la ligne de commande
# contient le motif, y compris un shell qui ne fait que le mentionner (il a tué mon propre
# shell de test le 07/09). On exige donc que l'exécutable soit réellement node/next avant
# de tuer : le motif désigne le candidat, `comm` décide.
for pid in $(pgrep -f "[n]ext-server|[n]ext dev" 2>/dev/null); do
  case "$(ps -p "$pid" -o comm= 2>/dev/null | tr -d ' ')" in
    node|next-server*|next*) kill -9 "$pid" 2>/dev/null || true ;;
  esac
done

# SUPERVISEUR CONCURRENT. Le 07/09, PM2 relançait le front dans les secondes suivant chaque
# arrêt : tous les nettoyages de ce script étaient donc annulés aussitôt, et le symptôme
# ressemblait à un orphelin tenace. On ne tue pas PM2 d'autorité — il peut superviser autre
# chose — mais on refuse de laisser croire que le nettoyage a abouti.
if command -v pm2 >/dev/null 2>&1 && pgrep -f "[P]M2.*God" >/dev/null 2>&1; then
  echo "  ⚠ PM2 tourne : il RELANCERA tout ce que ce script vient d'arrêter."
  echo "    Applications supervisées :"
  pm2 jlist 2>/dev/null | grep -oE '"name":"[^"]+"' | sed 's/^/      /' || true
  echo "    Pour lui retirer ce rôle :  pm2 delete all; pm2 save --force; pm2 kill"
fi
