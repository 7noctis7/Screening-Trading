"""Sommes-nous dans la fenêtre d'exécution ? — pour un cron qu'on n'a plus à retoucher.

  python scripts/fenetre_execution.py            # code 0 = agir, 1 = passer son tour

LE PROBLÈME QU'IL RÉSOUT. « Planifier une heure avant la clôture » ne se traduit pas par
une heure de cron fixe. La clôture de 16 h à New York tombe à 20 h UTC l'été et à 21 h
UTC l'hiver ; les changements d'heure américain et européen ne se font pas le même
dimanche, et une machine peut vivre dans n'importe quel fuseau. Une heure gelée dérive
donc au moins deux fois par an, et il faut y repenser à chaque fois.

LA SOLUTION. Le planificateur se réveille TOUTES LES HEURES et demande ici s'il doit
agir. La réponse se calcule dans l'heure du MARCHÉ, via le calendrier du projet — qui
connaît déjà les fériés NYSE et le passage à l'heure d'été. Une seule des vingt-quatre
tentatives quotidiennes tombe dans la fenêtre, quelle que soit la saison, quel que soit
le fuseau de la machine. Plus jamais de cron à corriger.

ET LE CRYPTO, LES JOURS FERMÉS. Il cote 24/7 : ni clôture, ni heure d'été, donc rien à
suivre — une heure UTC FIXE est ici le choix juste, à l'exact opposé des actions. Ce
second déclencheur ne s'arme QUE les jours sans séance NYSE : les jours de bourse, le
passage d'avant-clôture rebalance déjà tout, et en ajouter un second ferait payer deux
fois les frais pour le même portefeuille.

Le coût : vingt-trois réveils qui ne font rien. Ils sortent en silence — un journal
qu'on ne lit plus parce qu'il est plein de « rien à faire » ne protège de rien.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Minutes avant la clôture visées : la dernière heure, la plus liquide de la séance.
AVANT_CLOTURE_DEFAUT = 60.0
# Largeur de la fenêtre — un réveil horaire y tombe exactement une fois.
LARGEUR = 60.0
# CRYPTO, LES JOURS SANS SÉANCE. Le marché tourne 24/7 : il n'a ni clôture ni heure
# d'été, donc une heure UTC FIXE est ici le choix JUSTE, à l'exact opposé des actions.
# 00 h UTC est la frontière du jour boursier crypto — c'est là que se ferme la bougie
# quotidienne des sources du projet (klines Binance, `-USD` Yahoo). Rebalancer juste
# après, c'est décider sur des barres complètes plutôt qu'à cheval sur deux journées.
CRYPTO_HEURE_UTC_DEFAUT = 0


def cible() -> float:
    """Minutes avant la clôture visées. `QUANT_LIVE_AVANT_CLOTURE` pour changer."""
    try:
        brut = os.environ.get("QUANT_LIVE_AVANT_CLOTURE", "")
        v = float(brut or AVANT_CLOTURE_DEFAUT)
    except ValueError:
        return AVANT_CLOTURE_DEFAUT
    return v if v >= 0 else AVANT_CLOTURE_DEFAUT


def heure_crypto() -> int:
    """Heure UTC du passage crypto des jours fermés. `QUANT_CRYPTO_HEURE_UTC`."""
    try:
        brut = os.environ.get("QUANT_CRYPTO_HEURE_UTC", "")
        h = int(brut) if brut else CRYPTO_HEURE_UTC_DEFAUT
    except ValueError:
        return CRYPTO_HEURE_UTC_DEFAUT
    return h if 0 <= h <= 23 else CRYPTO_HEURE_UTC_DEFAUT


def passage_crypto(maintenant, heure: int) -> bool:
    """Faut-il faire le passage CRYPTO SEUL maintenant ?

    Uniquement les jours SANS séance — week-ends et fériés NYSE. Les jours de bourse,
    le passage d'avant-clôture rebalance déjà tout, crypto compris : ajouter un second
    déclenchement ferait deux rebalancements le même jour, donc deux fois les frais.
    """
    from packages.execution.market_calendar import est_jour_de_bourse
    return not est_jour_de_bourse(maintenant.date()) and maintenant.hour == heure


def dans_la_fenetre(restant: float | None, visee: float,
                    largeur: float = LARGEUR) -> bool:
    """La fenêtre est SEMI-OUVERTE — [visée − l/2, visée + l/2) — et c'est ce qui
    garantit qu'un réveil horaire y tombe exactement une fois. Fermée des deux côtés,
    une minute pile sur la borne déclencherait deux exécutions le même jour."""
    if restant is None:
        return False
    return visee - largeur / 2.0 <= restant < visee + largeur / 2.0


def main() -> int:
    ap = argparse.ArgumentParser(description="Fenêtre d'exécution avant clôture NYSE.")
    ap.add_argument("--verbeux", action="store_true",
                    help="dit aussi pourquoi il ne faut PAS agir")
    a = ap.parse_args()

    from datetime import UTC, datetime

    from packages.execution.market_calendar import (
        feries_a_jour,
        minutes_avant_cloture,
        raison_fermeture,
    )
    maintenant = datetime.now(UTC)
    restant = minutes_avant_cloture(maintenant)
    visee = cible()

    if passage_crypto(maintenant, heure_crypto()):
        print(f"fenêtre crypto : jour sans séance NYSE, {maintenant:%H h} UTC — "
              "le crypto cote 24/7, les actions seront reportées par run_live")
        return 0

    if dans_la_fenetre(restant, visee):
        print(f"fenêtre d'exécution : clôture dans {restant:.0f} min "
              f"(visée {visee:.0f})")
        if not feries_a_jour():
            print("⚠ la table des fériés NYSE ne couvre plus l'année en cours — "
                  "un jour férié pourrait passer pour une séance.", file=sys.stderr)
        return 0

    if a.verbeux:
        if restant is None:
            print(f"hors séance : {raison_fermeture(maintenant) or 'marché fermé'} "
                  f"— passage crypto à {heure_crypto():02d} h UTC les jours fermés")
        else:
            print(f"séance ouverte mais hors fenêtre : clôture dans {restant:.0f} min, "
                  f"visée {visee:.0f} ± {LARGEUR / 2:.0f}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
