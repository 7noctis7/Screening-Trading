#!/usr/bin/env python3
"""Cherche un horizon ou une classe d'actifs où le score PRÉDIT — avec correction de tests
multiples, sans laquelle on trouve toujours quelque chose.

LE PIÈGE QUE CE SCRIPT ÉVITE. Mesurer l'IC à 5, 21, 63 et 126 jours sur cinq classes
d'actifs fait vingt essais. À 5 % de seuil, on attend UN résultat « significatif » par pur
hasard. Publier le meilleur reviendrait à publier le plus chanceux : c'est ainsi qu'on
fabrique un edge qui n'existe pas, et l'opération est indétectable une fois le rapport
écrit. Benjamini-Hochberg contrôle le taux de fausses découvertes sur l'ENSEMBLE du
balayage — chaque cellule est donc jugée en sachant combien d'autres ont été tentées.

Tout est consigné au registre, y compris (surtout) les cellules rejetées : le compteur
d'essais déflate le Sharpe, et un balayage non consigné le fausserait à la hausse.

    python scripts/balayage_ic.py                       # 21 j, toutes classes
    python scripts/balayage_ic.py --horizons 5,21,63    # trois horizons
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

SORTIE = RACINE / "out" / "balayage_ic.json"


def _panel_par_classe(annees: int) -> tuple[dict, dict, str]:
    """(panel, classe par symbole, mode). Mêmes prix que la production, synthétiques exclus."""
    from datetime import timedelta

    from apps.api.snapshot import _load_prices, _seed_universe, _sector_of
    instruments = _seed_universe()
    classes = {m["symbol"]: (m.get("asset_class") or "equity") for m in instruments}
    secteurs = {m["symbol"]: _sector_of(m) for m in instruments}
    fin = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    data, mode, reels = _load_prices(instruments, secteurs,
                                     fin - timedelta(days=int(365.25 * annees)), fin, seed=7)
    return ({s: b for s, b in data.items() if s in reels and b}, classes, mode)


def _cellules(panel: dict, classes: dict, horizons: list[int], moteur,
              min_symboles: int) -> list[dict]:
    from packages.research.screening_ic import mesurer
    familles = {"toutes": panel}
    for classe in sorted({classes.get(s, "equity") for s in panel}):
        sous = {s: b for s, b in panel.items() if classes.get(s, "equity") == classe}
        if len(sous) >= min_symboles:
            familles[classe] = sous
    resultats = []
    for horizon in horizons:
        for nom, sous_panel in familles.items():
            print(f"  … {nom:12s} horizon {horizon:3d} j sur {len(sous_panel)} symboles", flush=True)
            mesure = mesurer(sous_panel, moteur, horizon=horizon)
            resultats.append({"classe": nom, "horizon": horizon,
                              "n_symboles": len(sous_panel), **mesure})
    return resultats


def _tableau(cellules: list[dict]) -> None:
    """Une ligne par essai, triée par p-valeur — les plus prometteurs en haut, et le
    verdict BH à côté, pour qu'on ne lise jamais l'IC sans savoir combien d'essais ont eu
    lieu."""
    def fmt(valeur, gabarit, largeur):
        return format("n/d" if valeur is None else format(valeur, gabarit), f">{largeur}")

    print()
    print(f"{'classe':12s} {'hor.':>5s} {'IC':>9s} {'t':>7s} {'p':>8s}  BH   robuste")
    ordre = sorted(cellules, key=lambda c: (c.get("p_valeur") is None, c.get("p_valeur") or 1.0))
    for c in ordre:
        print(f"{c['classe']:12s} {c['horizon']:5d} "
              f"{fmt(c.get('ic_moyen'), '+.4f', 9)} "
              f"{fmt(c.get('t_stat'), '+.2f', 7)} "
              f"{fmt(c.get('p_valeur'), '.4f', 8)}"
              f"  {'OUI' if c.get('significatif_apres_bh') else 'non':>3s}"
              f"  {'OUI' if c.get('robuste') else 'non'}")


def principal() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--horizons", default="21", help="jours de bourse, séparés par des virgules")
    ap.add_argument("--annees", type=int, default=8)
    ap.add_argument("--alpha", type=float, default=0.05, help="taux de fausses découvertes")
    ap.add_argument("--min-symboles", type=int, default=20,
                    help="taille minimale d'une classe pour être testée")
    args = ap.parse_args()
    horizons = [int(h) for h in args.horizons.split(",") if h.strip()]

    from packages.research.fdr import benjamini_hochberg
    from packages.research.ledger import append_record
    from packages.screening import ScreeningEngine

    panel, classes, mode = _panel_par_classe(args.annees)
    if len(panel) < args.min_symboles:
        print(f"✗ {len(panel)} symbole(s) à prix réels — trop peu. Lancer `make ingest`.")
        return 1
    moteur = ScreeningEngine.from_yaml(RACINE / "config" / "screening.yaml")
    print(f"→ {len(panel)} symboles réels (mode {mode}) · {len(horizons)} horizon(s)")
    cellules = _cellules(panel, classes, horizons, moteur, args.min_symboles)

    mesurables = [c for c in cellules if c.get("p_valeur") is not None]
    retenues = benjamini_hochberg([c["p_valeur"] for c in mesurables], alpha=args.alpha) \
        if mesurables else []
    for cellule, survit in zip(mesurables, retenues, strict=False):
        cellule["significatif_apres_bh"] = bool(survit)

    date = datetime.now(UTC).date().isoformat()
    for cellule in cellules:
        append_record({
            "date": date, "facteur": "screening_composite",
            "horizon": f"{cellule['horizon']}j", "classe": cellule["classe"],
            "statut": "promu" if (cellule.get("significatif_apres_bh")
                                  and cellule.get("robuste")) else "rejete",
            "these": (f"IC du score, classe « {cellule['classe']} », horizon "
                      f"{cellule['horizon']} j, corrigé Benjamini-Hochberg sur "
                      f"{len(mesurables)} essais simultanés."),
            "ic": cellule.get("ic_moyen"), "t_stat": cellule.get("t_stat"),
            "p_valeur": cellule.get("p_valeur"), "n_obs": cellule.get("n_dates"),
            "source": "make balayage-ic (réel)",
        })

    Path(SORTIE).parent.mkdir(parents=True, exist_ok=True)
    Path(SORTIE).write_text(json.dumps(
        {"date": date, "alpha": args.alpha, "n_essais": len(mesurables),
         "cellules": cellules}, indent=2, ensure_ascii=False), encoding="utf-8")

    _tableau(cellules)
    gagnantes = [c for c in cellules if c.get("significatif_apres_bh") and c.get("robuste")]
    print(f"\n{len(mesurables)} essais simultanés, seuil BH {args.alpha}.")
    print(f"→ {len(gagnantes)} cellule(s) significative(s) ET robuste(s)."
          + ("" if gagnantes else " Aucun edge démontré : la sélection reste un classement."))
    print(f"→ {SORTIE}  · toutes les cellules consignées au registre")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
