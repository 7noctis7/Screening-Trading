#!/usr/bin/env python3
"""Mesure l'IC walk-forward du score de screening sur les prix RÉELS locaux.

Coûteux (le moteur est réexécuté à chaque date de la grille) : on le lance à la main ou
par cron, et le résultat est ÉCRIT sur disque pour que l'API le publie sans recalculer.

    python scripts/mesurer_ic_screening.py                 # horizon 21 j
    python scripts/mesurer_ic_screening.py --horizon 63    # ~1 trimestre

Le fichier produit porte la date et le nombre de fenêtres : un résultat qu'on ne peut pas
dater ne peut pas être périmé, donc ne peut pas être contesté — c'est exactement ce qu'on
veut éviter dans un dépôt qui interdit les chiffres non traçables.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

SORTIE = RACINE / "out" / "ic_screening.json"


def _panel_reel(annees: int) -> tuple[dict, str]:
    """Même univers et mêmes prix que la production — jamais une seconde définition."""
    from datetime import timedelta

    from apps.api.snapshot import _load_prices, _seed_universe, _sector_of
    instruments = _seed_universe()
    secteurs = {m["symbol"]: _sector_of(m) for m in instruments}
    fin = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    debut = fin - timedelta(days=int(365.25 * annees))
    data, mode, reels = _load_prices(instruments, secteurs, debut, fin, seed=7)
    # Prix SYNTHÉTIQUES exclus : mesurer un IC dessus produirait un chiffre sur des séries
    # inventées — précisément ce que le mandat données-réelles interdit.
    return {s: b for s, b in data.items() if s in reels and b}, mode


def _consigner(resultat: dict, horizon: int) -> None:
    """Écrit la mesure au registre des hypothèses — y compris (surtout) quand elle échoue.

    Deux raisons, et la seconde est la moins intuitive. (1) Une hypothèse rejetée doit
    rester citable, sinon elle sera re-testée dans six mois par quelqu'un qui aura oublié.
    (2) Chaque mesure est un ESSAI : elle incrémente le compteur qui déflate le Sharpe
    (DSR, López de Prado). Ne consigner que les succès ferait mécaniquement grimper la
    significativité apparente de ce qui reste — c'est la définition du p-hacking, et un
    registre qui ne garde que ce qui marche l'organise au lieu de s'en prémunir.
    """
    from packages.research.ledger import append_record
    significatif = abs(resultat.get("t_stat") or 0.0) >= 2.0
    statut = "promu" if (resultat.get("robuste") and significatif) else "rejete"
    append_record({
        "date": datetime.now(UTC).date().isoformat(),
        "facteur": "screening_composite",
        "horizon": f"{horizon}j",
        "statut": statut,
        "these": (f"IC transversal du score de screening à {horizon} jours "
                  f"(Spearman, fenêtres disjointes, coupe hors échantillon chronologique)."),
        "params": {"horizon": horizon, "pas": resultat.get("pas"),
                   "n_symboles": resultat.get("n_symboles")},
        "ic": resultat.get("ic_moyen"), "t_stat": resultat.get("t_stat"),
        "n_obs": resultat.get("n_dates"),
        "ic_is": resultat.get("ic_premiere_moitie"),
        "ic_oos": resultat.get("ic_seconde_moitie"),
        "source": "make ic-screening (réel)",
    })
    print(f"→ consigné au registre des hypothèses : {statut}")


def principal() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--horizon", type=int, default=21, help="jours de bourse (défaut 21)")
    ap.add_argument("--annees", type=int, default=8, help="profondeur d'historique")
    ap.add_argument("--sortie", default=str(SORTIE))
    args = ap.parse_args()

    from packages.research.screening_ic import mesurer
    from packages.screening import ScreeningEngine

    panel, mode = _panel_reel(args.annees)
    if len(panel) < 20:
        print(f"✗ {len(panel)} symbole(s) à prix réels — trop peu pour un IC transversal.")
        print("  Alimentez la base (`make ingest`) avant de mesurer.")
        return 1
    moteur = ScreeningEngine.from_yaml(RACINE / "config" / "screening.yaml")
    print(f"→ {len(panel)} symboles réels (mode {mode}), horizon {args.horizon} j…")
    resultat = mesurer(panel, moteur, horizon=args.horizon)
    resultat |= {"mesure_le": datetime.now(UTC).isoformat(timespec="seconds"),
                 "n_symboles": len(panel), "mode_donnees": mode,
                 "config": "config/screening.yaml"}

    _consigner(resultat, args.horizon)

    chemin = Path(args.sortie)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(resultat, indent=2, ensure_ascii=False), encoding="utf-8")

    if not resultat.get("available"):
        print(f"UNCALIBRATED — {resultat.get('reason')}")
        return 0
    print(f"  IC moyen      : {resultat['ic_moyen']:+.4f}  sur {resultat['n_dates']} fenêtres disjointes")
    t = resultat.get("t_stat")
    print(f"  t-stat        : {t:+.2f}" if t is not None else "  t-stat        : n/d")
    print(f"  1re / 2e moitié : {resultat['ic_premiere_moitie']:+.4f} / {resultat['ic_seconde_moitie']:+.4f}")
    print(f"  robuste       : {'OUI' if resultat['robuste'] else 'NON'}")
    print(f"→ écrit dans {chemin}")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
