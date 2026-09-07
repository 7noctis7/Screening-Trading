#!/usr/bin/env bash
# Arrêt des services locaux (API uvicorn + front Next). Utilisé par `make stop` ET par
# `scripts/start.sh` : une seule définition de ce qu'on tue, donc aucune divergence
# possible entre les deux chemins.
set -u
cd "$(dirname "$0")/.."

# `pkill -f "uvicorn apps.api.main"` SE TUAIT LUI-MÊME depuis une ligne de Makefile :
# make exécute la recette via `/bin/sh -c '…'` dont la ligne de commande CONTIENT le
# motif. pkill terminait donc ce shell, make affichait « [Makefile:43: stop] Terminated »
# et les nettoyages de ports qui suivaient n'étaient JAMAIS exécutés — un arrêt qui
# semblait échouer bruyamment tout en s'arrêtant à mi-course (mesuré le 07/09).
# Les crochets cassent l'auto-correspondance sans changer la cible : le motif exige un
# point littéral là où le shell appelant porte un crochet.
pkill -f "uvicorn apps[.]api[.]main" 2>/dev/null || true

# `kill -9 $(lsof -ti:PORT)` est aveugle : il tue CE QUI TIENT le port, quoi que ce soit.
# Le 07/09 il a tué un tunnel `ssh -L 3000:… -L 8000:…` ouvert sur cette machine, et avec
# lui la session qui exécutait `make start`. Un tunnel n'est pas un service à redémarrer :
# on le signale, on ne le tue pas.
for port in 8000 3000; do
  for pid in $(lsof -ti:"$port" 2>/dev/null); do
    nom="$(ps -p "$pid" -o comm= 2>/dev/null | tr -d ' ')"
    case "$nom" in
      ssh|sshd)
        echo "  ⚠ port $port tenu par $nom (PID $pid) — NON tué : c'est un tunnel, pas un service."
        echo "    Fermez-le depuis la machine qui l'a ouvert, ou changez de port."
        ;;
      *) kill -9 "$pid" 2>/dev/null || true ;;
    esac
  done
done
