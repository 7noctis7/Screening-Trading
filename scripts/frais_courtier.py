#!/usr/bin/env python3
"""Les frais du courtier, et l'identité qu'ils referment.

LA QUESTION (18/09) : « avec 100 000 $ de mise, 1 196,63 $ de réalisé et 587,12 $ de
latent, je ne retombe pas sur mes 100 973,45 $ — il manque 810,30 $. »

LA RÉPONSE EST STRUCTURELLE, PAS ARITHMÉTIQUE. Le journal est reconstruit depuis les
seuls ORDRES exécutés ; or un fill porte une quantité et un prix, jamais son coût de
transaction. Chez Alpaca les frais sont des ACTIVITÉS séparées — `FEE` en dollars
(TAF/REG/CAT), `CFEE` pour la crypto. Le réalisé reconstruit est donc BRUT, et
l'identité y perd exactement le montant des frais.

    capital = mise + réalisé BRUT + latent − FRAIS

CE QUE CE SCRIPT NE FAIT PAS : estimer. Le taux de 0,220 % retrouvé sur neuf actifs
suffirait à fabriquer un chiffre plausible — et un chiffre plausible qui ne vient pas
d'une mesure est exactement ce que ce dépôt refuse. On lit donc les activités RÉELLES,
on affiche ce qu'elles disent, et si l'identité ne se referme pas, le reste est NOMMÉ.

    python scripts/frais_courtier.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MISE = 100_000.00        # `Journal cash between accounts` du 2026-06-17, lu chez Alpaca


def _mesures() -> dict:
    from packages.execution.alpaca_broker import AlpacaBroker
    from packages.execution.perimetre_journal import pris_par_le_robot
    from packages.storage import SqliteTradeJournal
    b = AlpacaBroker(paper=True)
    pos = b.positions_detailed()
    lots = SqliteTradeJournal().all()
    fermes = [t for t in lots if t.exit_ts]
    return {
        "equity": round(float(b.equity()), 2),
        "latent": round(sum(float(p.get("pnl") or 0.0) for p in pos), 2),
        "realise_brut": round(sum(float(t.pnl_net or 0.0) for t in fermes), 2),
        "n_fermes": len(fermes),
        "n_robot": sum(1 for t in fermes if pris_par_le_robot(t.id)),
        "frais": b.frais(),
    }


def main() -> int:
    print(__doc__.split("    python")[0].rstrip())
    try:
        m = _mesures()
    except Exception as e:  # noqa: BLE001
        print(f"\n  ✗ COURTIER ILLISIBLE : {str(e)[:160]}")
        return 2

    f = m["frais"]
    print(f"\n  FRAIS LUS DANS LES ACTIVITÉS DU COMPTE — {f.get('n', 0)} activité(s)")
    if not f.get("disponible"):
        print(f"    ✗ indisponible : {f.get('motif')}")
        print("      Sans eux, l'écart ci-dessous reste NOMMÉ, jamais comblé.")
    else:
        for typ, montant in sorted(f.get("par_type", {}).items()):
            print(f"    {typ:<6} {montant:>12,.2f} $".replace(",", " "))
        print(f"    {'TOTAL':<6} {f.get('total_usd', 0.0):>12,.2f} $"
              .replace(",", " "))
        if f.get("n_en_nature"):
            print(f"    + {f['n_en_nature']} prélèvement(s) EN JETONS, sans montant en")
            print("      dollars : leur trace est dans la valeur du portefeuille.")

    frais = abs(float(f.get("total_usd") or 0.0)) if f.get("disponible") else 0.0
    attendu = MISE + m["realise_brut"] + m["latent"] - frais
    residu = m["equity"] - attendu
    print("\n  L'IDENTITÉ — capital = mise + réalisé BRUT + latent − frais\n")
    for lib, val in (("mise initiale (JNLC 2026-06-17)", MISE),
                     (f"+ réalisé BRUT ({m['n_fermes']} aller-retours)",
                      m["realise_brut"]),
                     ("+ latent des positions réelles", m["latent"]),
                     ("− frais prélevés par le courtier", -frais)):
        print(f"    {lib:<42} {val:>12,.2f} $".replace(",", " "))
    print(f"    {'':<42} {'':->12}")
    print(f"    {'= attendu':<42} {attendu:>12,.2f} $".replace(",", " "))
    print(f"    {'capital réel constaté':<42} {m['equity']:>12,.2f} $"
          .replace(",", " "))
    print(f"    {'ÉCART RÉSIDUEL':<42} {residu:>+12,.2f} $".replace(",", " "))
    if abs(residu) <= max(25.0, 0.0005 * m["equity"]):
        print("\n    ✓ L'identité se referme au frottement près.")
    else:
        print("\n    ⚠ Écart NON expliqué. Il n'est pas comblé ici — il est nommé,")
        print("      et c'est là qu'il faut chercher.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
