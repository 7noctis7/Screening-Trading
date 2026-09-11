#!/usr/bin/env python3
"""Le régime « haute volatilité » de la spec, mesuré sur la base RÉELLE.

CE QUE CE BANC TRANCHE, ET POURQUOI IL PASSE AVANT LE CODE DE BASCULE. La spec propose
de basculer sur un modèle dédié quand l'ATR dépasse 200 % de sa moyenne 30 périodes.
Écrire la bascule d'abord, c'est se condamner à ne jamais savoir si elle sert : une
règle inerte (qui ne mord jamais) et une règle utile produisent le même code, les mêmes
tests verts, et le même sentiment de progrès.

Trois questions, dans cet ordre — la troisième peut clore le sujet à elle seule :

  1. Combien de barres franchissent le seuil ? (une règle inerte se lit comme « géré »)
  2. Les rendements futurs diffèrent-ils entre les deux régimes ? (sinon, couper
     l'échantillon en deux ne fait que le diviser)
  3. Reste-t-il, du côté haute volatilité, de quoi ENTRAÎNER quoi que ce soit ?
     `_ml_section` refuse sous 500 lignes. Si le régime rare n'atteint pas ce plancher,
     le modèle dédié n'existera pas, et la bascule n'a pas d'objet.

    python scripts/regime_atr_lab.py              # seuil de la spec (2,0), horizon 5 j
    python scripts/regime_atr_lab.py 1.5 2.0 2.5      # plusieurs seuils
    python scripts/regime_atr_lab.py --horizon 10

Lecture seule : aucune écriture, aucun ordre, aucune décision. Le banc rend un compte.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.research import regime_atr as R  # noqa: E402

MIN_BARRES = R.FENETRE_ATR + R.FENETRE_MOYENNE + R.HORIZON + 20


def _donnees():
    """Le MÊME univers et la même fenêtre que la production — sinon on mesure
    autre chose et l'écart constaté ne se rapporte à rien de connu."""
    from apps.api.snapshot import (
        _HISTORY_DAYS,
        _load_prices,
        _sector_of,
        _seed_universe,
    )
    instruments = _seed_universe()
    secteur = {m["symbol"]: _sector_of(m) for m in instruments}
    fin = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    debut = fin - timedelta(days=_HISTORY_DAYS)
    data, mode, reels = _load_prices(instruments, secteur, debut, fin, 7)
    if len(reels) >= 30:        # zéro prix synthétique dans un banc de décision
        data = {s: b for s, b in data.items() if s in reels}
    return data, mode, len(reels)


def _utilisable(barres) -> bool:
    """Un high égal au low sur toute la série est une base close-only déguisée.

    Le piège a déjà coûté une mesure cette année (comblement MFE) : « non vide » n'est
    pas « exploitable ». Un ATR calculé sur des barres sans amplitude vaut zéro partout,
    et zéro partout produit un ratio indéfini qu'on lirait comme « régime calme ».
    """
    if len(barres) < MIN_BARRES:
        return False
    return any(b.high > b.low for b in barres[-MIN_BARRES:])


def mesurer(data: dict, seuil: float, horizon: int) -> dict:
    """Agrège les rendements des deux régimes sur tout l'univers."""
    haute: list[float] = []
    basse: list[float] = []
    haute_d: list[tuple[str, float]] = []
    basse_d: list[tuple[str, float]] = []
    retenus, ecartes = 0, 0
    ratios_max: list[float] = []
    for barres in data.values():
        if not _utilisable(barres):
            ecartes += 1
            continue
        retenus += 1
        d = R.classer([b.high for b in barres], [b.low for b in barres],
                      [b.close for b in barres], dates=[b.ts for b in barres],
                      seuil=seuil, horizon=horizon)
        haute.extend(d["haute"])
        basse.extend(d["basse"])
        haute_d.extend(d["haute_datees"])
        basse_d.extend(d["basse_datees"])
        if d["ratio_max"] is not None:
            ratios_max.append(d["ratio_max"])
    v = R.verdict(haute, basse, seuil=seuil,
                  haute_datees=haute_d, basse_datees=basse_d)
    v["symboles_retenus"] = retenus
    v["symboles_ecartes"] = ecartes
    v["ratio_max_median"] = R._mediane(ratios_max)
    return v


def rapport(v: dict, horizon: int) -> str:
    def pct(x):
        return "n/d" if x is None else f"{x * 100:+.3f} %"

    lignes = [
        f"SEUIL {v['seuil']:.2f} × moyenne({R.FENETRE_MOYENNE})"
        f" de l'ATR({R.FENETRE_ATR}) · horizon {horizon} j",
        f"  symboles      : {v['symboles_retenus']} retenus,"
        f" {v['symboles_ecartes']} écartés (barres insuffisantes ou sans amplitude)",
        f"  barres        : {v['n_haute']} haute vol · {v['n_basse']} basse vol"
        + (f" · part haute {v['part_haute'] * 100:.2f} %"
           if v["part_haute"] else ""),
        "  ratio max médian par symbole : "
        + ("n/d" if v["ratio_max_median"] is None
           else f"{v['ratio_max_median']:.2f}"),
        f"  rendement {horizon} j moyen  : haute {pct(v['rendement_moyen_haute'])}"
        f" · basse {pct(v['rendement_moyen_basse'])}",
        f"  entraînable ({R.PLANCHER_ENTRAINEMENT} lignes) : "
        f"haute {'OUI' if v['entrainable_haute'] else 'NON'}"
        f" · basse {'OUI' if v['entrainable_basse'] else 'NON'}",
    ]
    w = v.get("welch") or {}
    if w.get("disponible"):
        lignes.append(f"  Welch BRUT    : t = {w['t']} sur {w['ddl']} ddl"
                      f" · écart de moyenne {pct(w['ecart_moyen'])}"
                      "  ← compte chaque (symbole, jour) comme un tirage")
    if v.get("n_jours_haute") is not None:
        lignes.append(f"  épisodes      : {v['n_jours_haute']} JOURNÉES de haute vol"
                      f" · {v['n_jours_basse']} de basse vol")
        wg = v.get("welch_groupe") or {}
        if wg.get("disponible"):
            lignes.append(f"  Welch GROUPÉ  : t = {wg['t']} sur {wg['ddl']} ddl"
                          f" · écart de moyenne {pct(wg['ecart_moyen'])}"
                          "  ← une observation par journée de marché")
        else:
            lignes.append(f"  Welch GROUPÉ  : indisponible ({wg.get('motif')})")
    lignes.append("  fenêtres SANS chevauchement (une observation tous les"
                  f" {horizon} jours) — sinon n serait gonflé d'un facteur {horizon}"
                  " par des jours partagés.")
    lignes.append("  Un pic d'ATR est un ÉVÉNEMENT DE MARCHÉ : tout l'univers le")
    lignes.append("  traverse le même jour. Seul le t groupé compte des épisodes ;")
    lignes.append("  c'est lui, et non le t brut, qui décide du verdict.")
    lignes.append(f"  VERDICT       : {v['statut']} — {v['message']}")
    return "\n".join(lignes)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("seuils", nargs="*", type=float, default=None,
                    help=f"seuils à éprouver (défaut : {R.SEUIL_SPEC}, la spec)")
    ap.add_argument("--horizon", type=int, default=R.HORIZON,
                    help="rendement futur mesuré, en jours ouvrés")
    a = ap.parse_args()
    seuils = a.seuils or [R.SEUIL_SPEC]

    print("Chargement des prix…")
    data, mode, n_reels = _donnees()
    print(f"Mode : {mode} · univers {len(data)} · séries réelles {n_reels}\n")
    if mode != "real" and n_reels < 30:
        print("⛔ Pas assez de séries RÉELLES — un régime calibré sur du synthétique")
        print("   ne dit rien du marché. Mesure abandonnée.")
        raise SystemExit(1)

    for s in seuils:
        print(rapport(mesurer(data, s, a.horizon), a.horizon))
        print()
    print("Ce banc MESURE. Il n'active rien : toute bascule de modèle passe d'abord")
    print("par les gates de vault/15_CERTIFICATION.md.")


if __name__ == "__main__":
    main()
