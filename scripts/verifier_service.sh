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
      echo "  Votre navigateur parle à un processus qui n'est pas celui que systemd surveille."
      # La FILIATION observée, imprimée sur place. Deux fois le 07/09 ce verdict est tombé
      # sans que je puisse dire s'il désignait un vrai orphelin ou un enfant légitime que ma
      # remontée manquait. Un diagnostic qui ne montre pas ce qu'il a vu oblige à le
      # redemander ; celui-ci se suffit.
      echo "  Filiation observée :"
      _p="$tenant"
      for _ in 1 2 3 4 5 6; do
        printf '    %s  %s  (parent %s)\n' "$_p" \
          "$(ps -p "$_p" -o comm= 2>/dev/null || echo '?')" \
          "$(ps -p "$_p" -o ppid= 2>/dev/null | tr -d ' ' || echo '?')"
        _p="$(ps -p "$_p" -o ppid= 2>/dev/null | tr -d ' ')"
        { [ -z "$_p" ] || [ "$_p" = "1" ] || [ "$_p" = "0" ]; } && break
      done
      echo "  Processus du service (cgroup) :"
      systemctl status quant-web.service --no-pager 2>/dev/null \
        | sed -n '/CGroup/,$p' | head -6 | sed 's/^/    /'
      # UN AUTRE GESTIONNAIRE DE PROCESSUS. Diagnostiqué le 07/09 après une journée à
      # accuser des « orphelins » : PM2 faisait tourner le front et le RESSUSCITAIT dans
      # les secondes suivant chaque kill. Tuer le processus ne servait donc à rien — il
      # fallait retirer le superviseur concurrent. Un processus qui renaît n'est pas un
      # orphelin : c'est quelqu'un qui le redémarre.
      if ps -p "$tenant" -o ppid= >/dev/null 2>&1 && pgrep -a "PM2|pm2" >/dev/null 2>&1; then
        echo "  ⚠ PM2 TOURNE SUR CETTE MACHINE et supervise probablement ce processus."
        echo "    Deux gestionnaires ne peuvent pas se partager le port 3000. Le tuer ne"
        echo "    suffit pas : PM2 le relance. Retirer PM2 de ce rôle :"
        echo "        pm2 delete all; pm2 save --force; pm2 kill"
        echo "        sudo systemctl disable --now pm2-\$USER"
      fi
      echo "  Si le PID $tenant figure dans le cgroup ci-dessus, c'est MA remontée qui échoue"
      echo "  — envoyez ce bloc. Sinon, voir ci-dessus, ou :   sudo kill -9 $tenant && make up"
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
  # « 200 » dit qu'un PROCESSUS répond. Il ne dit pas que l'API peut SERVIR une page :
  # sans snapshot en cache, la première requête en construit un (1 à 3 min) pendant
  # lesquelles toutes les pages restent sur leurs squelettes. Vert ici, écran qui tourne
  # là-bas — c'est exactement le décalage qui a coûté une heure de diagnostic le 21/09,
  # et c'est le même raisonnement que l'en-tête de ce fichier tient pour le front.
  # La route est à coût constant (elle ne touche pas au snapshot) : l'interroger est sûr.
  sante="$(curl -s --max-time 5 http://127.0.0.1:8000/health || true)"
  printf "✓ API %s\n" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:8000/health || echo 000)"
  QT_SANTE="$sante" python3 - <<'PYSANTE' || true
import json
import os

try:
    d = json.loads(os.environ.get("QT_SANTE") or "{}")
except Exception:
    d = {}
msg = d.get("message")
if not msg:
    print("  ? état du snapshot ILLISIBLE — API d'une version antérieure, ou réponse "
          "inattendue. Ne pas conclure que tout va bien.")
else:
    age = d.get("age_s")
    suffixe = f" (âge {age:.0f} s)" if isinstance(age, (int, float)) else ""
    marque = "✓" if d.get("sert_immediatement") else "⚠"
    print(f"  {marque} snapshot {d.get('snapshot')}{suffixe} — {msg}")
PYSANTE
  # LE PIÈGE DU TUNNEL, mesuré et non supposé (21/09).
  #
  # Les services n'écoutent que sur IPv4 (`--host 127.0.0.1`). Or `ssh -L 3000:localhost:3000`
  # résout « localhost » SUR LE VPS, où il peut valoir `::1`. SSH tente alors une adresse que
  # personne n'écoute et répond, en boucle :
  #
  #     channel 5: open failed: connect failed: Connection refused
  #
  # …pendant que le site, lui, fonctionne parfaitement. Vu du navigateur c'est « aucune page
  # ne se charge » ; vu d'ici, tout est vert. Les deux sont vrais, et rien ne les reliait.
  # On ne DEVINE pas la pile écoutée : on essaie `[::1]`, et on ne parle que si ça refuse.
  if ! curl -s -o /dev/null --max-time 2 "http://[::1]:$PORT/" 2>/dev/null; then
    ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
    echo "  ↪ écoute IPv4 seulement (rien sur [::1]:$PORT). Depuis une autre machine, le"
    echo "    tunnel doit viser 127.0.0.1 — « localhost » y résout ::1 et SSH répondra"
    echo "    « channel N: open failed: connect failed: Connection refused » :"
    echo "       ssh -L $PORT:127.0.0.1:$PORT -L 8000:127.0.0.1:8000 $(id -un)@${ip:-<vps>}"
  fi
fi
exit "$statut"
