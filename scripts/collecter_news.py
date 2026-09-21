#!/usr/bin/env python3
"""Accumule le corpus de news DATÉES — à lancer tous les jours, sans exception.

  python scripts/collecter_news.py                 # univers mobile (top 200 + watchlist)
  python scripts/collecter_news.py --symboles AAPL MSFT NVDA
  python scripts/collecter_news.py --etat          # où en est le corpus, sans rien collecter

POURQUOI C'EST URGENT ET PAS IMPORTANT. Mesurer si un modèle de langage apporte un alpha
incrémental exige des news datées ET leur TEXTE — pour pouvoir les re-scorer avec un autre
modèle et comparer. Le dépôt sait tout faire sauf garder ce texte : `data/news.csv` n'existe
pas, et `.cache/sentiment_history` ne conserve que des scores agrégés, irréversibles.

Un flux RSS ne se rejoue pas. Chaque jour sans collecte est un jour PERDU DÉFINITIVEMENT :
lancer ce script dans trois mois donnera un corpus de trois mois, pas de six. C'est la seule
tâche de tout ce chantier dont le coût augmente avec le retard.

Ce script ne décide rien, n'entraîne rien, n'envoie aucun ordre. Il écrit des titres.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PAR_SYMBOLE = 12
PLAFOND_SYMBOLES = 200     # une collecte qui dure une heure ne tourne pas tous les jours


def _univers(limite: int) -> list[str]:
    """Univers mobile si disponible (top 200 + watchlist), sinon les seeds."""
    cfg = ROOT / "config" / "mobile_universe.csv"
    if cfg.exists():
        with cfg.open(encoding="utf-8") as f:
            syms = [r["symbol"].strip() for r in csv.DictReader(f)
                    if r.get("symbol") and (r.get("asset_class") or "").lower()
                    in ("equity", "etf", "")]
        if syms:
            return syms[:limite]
    from apps.api.snapshot import _seed_universe
    return [m["symbol"] for m in _seed_universe()
            if m.get("asset_class") in ("equity", "etf")][:limite]


def _afficher_etat() -> int:
    from packages.sentiment.corpus import CHEMIN, etat
    e = etat()
    if not e["disponible"]:
        print(f"⛔ {e['motif']}")
        print(f"   Attendu : {CHEMIN}")
        return 1
    print(f"\n  Corpus : {e['n']} titre(s) · {e['n_symboles']} symbole(s) · "
          f"{e['n_jours']} jour(s)")
    print(f"  Période : {e['du']} → {e['au']}")
    print(f"  Rétro-publiés : {e['retro_publies']} ({e['part_retro']:.1%}) — découverts "
          "APRÈS leur date de publication")
    print("    C'est la fuite qu'on aurait introduite en se fiant à `date` seule.")
    # Un ordre de grandeur, pas un seuil : une étude d'événement sur quelques centaines
    # d'observations ne conclut rien, et le dire évite de croire à un résultat trop tôt.
    if e["n"] < 500:
        print(f"\n  ⚠ {e['n']} observations : très en dessous de ce qu'exige une étude "
              "d'événement. Continuer à collecter avant toute conclusion.")
    print()
    return 0


def collecter(symboles: list[str], verbeux: bool) -> dict:
    from packages.sentiment.corpus import ajouter, normaliser
    from packages.sentiment.sources import fetch_company_news
    lignes: list[dict] = []
    sans_date = muets = 0
    for i, sym in enumerate(symboles, 1):
        try:
            brutes = fetch_company_news(sym, limit=PAR_SYMBOLE)
        except Exception:  # noqa: BLE001 — un symbole qui échoue n'arrête pas la collecte
            brutes = []
        if not brutes:
            muets += 1
        for b in brutes:
            n = normaliser(b, sym)
            if n is None:
                sans_date += 1
                continue
            lignes.append(n)
        if verbeux and i % 25 == 0:
            print(f"  … {i}/{len(symboles)} symboles, {len(lignes)} titre(s) retenus")
    res = ajouter(lignes)
    # Les titres SANS DATE sont comptés et non ajoutés : leur donner la date du jour leur
    # prêterait une fraîcheur qu'ils n'ont pas, dans un jeu qui sert à mesurer la prédiction.
    return {**res, "sans_date": sans_date, "symboles_muets": muets,
            "symboles": len(symboles)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--symboles", nargs="*", default=None)
    ap.add_argument("--max-symboles", type=int, default=PLAFOND_SYMBOLES)
    ap.add_argument("--etat", action="store_true", help="afficher l'état sans collecter")
    ap.add_argument("--silencieux", action="store_true")
    a = ap.parse_args()

    if a.etat:
        return _afficher_etat()

    symboles = a.symboles or _univers(a.max_symboles)
    if not a.silencieux:
        print(f"Collecte de news sur {len(symboles)} symbole(s)…")
    r = collecter(symboles, verbeux=not a.silencieux)
    print(f"✅ {r['ajoutees']} titre(s) ajouté(s) · {r['doublons']} déjà connu(s) · "
          f"{r['sans_date']} sans date (ignorés) · {r['symboles_muets']} symbole(s) muets "
          f"· corpus : {r['total']}")
    if r["total"] == 0:
        print("⚠ Corpus toujours vide : réseau indisponible ou flux inaccessibles.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
