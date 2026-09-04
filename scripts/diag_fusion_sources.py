#!/usr/bin/env python3
"""Les bases de prix sont-elles d'accord ? On MESURE, on ne suppose pas.

POURQUOI CE SCRIPT EXISTE. Le dépôt fusionnait `YAHOO.db` et `market.db` selon deux
règles OPPOSÉES — `_load_prices` gardait le premier provider, `merge_bars` gardait le
dernier — et personne ne pouvait dire laquelle des deux lectures était affichée. L'écart
mesuré sur le cœur QQQ valait 0,71 %/an. La règle est désormais unique (la base longue
prime, la maj quotidienne comble les trous ; cf. `packages/data/fusion_sources`).

Reste la question que la règle ne répond pas : **de combien les bases divergent-elles
là où elles se recouvrent ?** Tant qu'on ne l'a pas mesuré, « elles sont d'accord » est
une hypothèse. Ce script la met en chiffres, symbole par symbole :

  · combien de jours chaque source a RÉELLEMENT fournis (lignage) ;
  · sur combien de jours les deux se recouvrent ;
  · combien de ces jours portent un cours DIFFÉRENT, et de combien.

Un désaccord ne dit pas laquelle a raison. Il dit que le choix de priorité CHANGE le
résultat — donc qu'il doit être motivé plutôt que subi.

    python scripts/diag_fusion_sources.py                # univers mobile
    python scripts/diag_fusion_sources.py QQQ SPY AAPL   # symboles choisis
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MAX_SYMBOLES = 40          # au-delà, la sortie cesse d'être lisible
JOURS = 4015               # même profondeur que la production (QUANT_HISTORY_DAYS)


def _bases() -> list[tuple[Path, str]]:
    """Bases présentes, DANS L'ORDRE DE PRIORITÉ de la fusion."""
    from apps.api.snapshot import _price_db_path
    brutes = [(_price_db_path(), "base longue"),
              (ROOT / "data" / "market.db", "maj quotidienne"),
              (ROOT / "data" / "crypto.db", "crypto")]
    return [(Path(p), n) for p, n in brutes if p is not None and Path(p).exists()]


def _series(bases: list[tuple[Path, str]], symbole: str, depuis) -> dict[str, dict]:
    """{source: {jour: close}} — une lecture INDÉPENDANTE par base, sans fusion.

    C'est le point : pour comparer deux sources il faut les lire séparément. Une fois
    fusionnées, la source perdante a disparu et le désaccord avec elle."""
    from packages.data.fusion_sources import jour
    from packages.data.providers.db_provider import DBPriceProvider
    out: dict[str, dict] = {}
    for chemin, nom in bases:
        try:
            bars = DBPriceProvider(chemin).fetch_ohlcv(symbole, "1d", depuis, None)
        except Exception:  # noqa: BLE001 — base illisible : elle ne dira rien, c'est tout
            continue
        if bars:
            out[nom] = {jour(b.ts): float(b.close) for b in bars}
    return out


def _ligne(symbole: str, par_source: dict[str, dict]) -> dict | None:
    """Une ligne de mesure, ou None si moins de deux sources portent le symbole."""
    from packages.data.fusion_sources import desaccords
    if len(par_source) < 2:
        return None
    jours = [set(s) for s in par_source.values()]
    commun = set.intersection(*jours)
    ecarts = desaccords(par_source)
    pire = max((d["ecart_relatif"] for d in ecarts), default=0.0)
    return {"symbole": symbole, "sources": {n: len(s) for n, s in par_source.items()},
            "commun": len(commun), "desaccords": len(ecarts), "pire": pire,
            "exemples": ecarts[:3]}


def _symboles(argv: list[str]) -> list[str]:
    demandes = [a for a in argv[1:] if not a.startswith("-")]
    if demandes:
        return demandes[:MAX_SYMBOLES]
    csv = ROOT / "config" / "mobile_universe.csv"
    if not csv.exists():
        return ["QQQ", "SPY", "AAPL"]
    lignes = csv.read_text(encoding="utf-8").splitlines()[1:]
    return [x.split(",")[0].strip() for x in lignes if x.strip()][:MAX_SYMBOLES]


def _afficher(lignes: list[dict], bases: list[tuple[Path, str]]) -> None:
    print(f"\n  {len(bases)} base(s) lisibles, par ordre de priorité :")
    for chemin, nom in bases:
        print(f"    {nom:<18} {chemin.name}")
    if not lignes:
        print("\n  Aucun symbole n'est porté par DEUX bases : aucun recouvrement, "
              "donc aucun désaccord possible.")
        return
    print(f"\n  {'symbole':<10} {'commun':>8} {'désaccords':>11} {'pire écart':>11}   "
          "jours par source")
    print("  " + "-" * 78)
    for r in sorted(lignes, key=lambda x: -x["desaccords"]):
        srcs = " · ".join(f"{n} {c}" for n, c in r["sources"].items())
        print(f"  {r['symbole']:<10} {r['commun']:>8} {r['desaccords']:>11} "
              f"{r['pire'] * 100:>10.4f}%   {srcs}")
    total = sum(r["desaccords"] for r in lignes)
    touches = sum(1 for r in lignes if r["desaccords"])
    print(f"\n  {touches}/{len(lignes)} symbole(s) en désaccord · "
          f"{total} jour(s) au total")
    pire = max(lignes, key=lambda x: x["pire"])
    if pire["pire"] > 0:
        print(f"\n  PIRE CAS — {pire['symbole']}, écart de "
              f"{pire['pire'] * 100:.4f} % :")
        for d in pire["exemples"]:
            vals = " · ".join(f"{n} {v:.4f}" for n, v in d["valeurs"].items())
            print(f"    {d['jour']}   {vals}")
        print("\n  Un désaccord ne dit pas quelle source a raison. Il dit que la")
        print("  PRIORITÉ change le résultat — donc qu'elle doit être motivée.")
    else:
        print("\n  Aucun désaccord au-delà de l'arrondi : sur les dates communes, les")
        print("  bases disent la même chose. La priorité ne change alors que la")
        print("  COUVERTURE, pas les valeurs.")


def main() -> None:
    print(__doc__.split("    python")[0].rstrip())
    from datetime import UTC, datetime, timedelta
    bases = _bases()
    if len(bases) < 2:
        print(f"\n  {len(bases)} base présente — il en faut deux pour comparer.")
        return
    depuis = datetime.now(UTC) - timedelta(days=JOURS)
    lignes = []
    for sym in _symboles(sys.argv):
        ligne = _ligne(sym, _series(bases, sym, depuis))
        if ligne:
            lignes.append(ligne)
    _afficher(lignes, bases)


if __name__ == "__main__":
    main()
