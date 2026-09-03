#!/usr/bin/env python3
"""Le journal et le compte disent-ils la même chose ? On MESURE, on ne déduit pas.

D'OÙ VIENT CE SCRIPT. Le 03/09 j'ai AFFIRMÉ que les lots ouverts portaient « environ
-5 600 $ de latent », en rapprochant l'espérance affichée (39 × 149,27 $) du rendement
du compte (+0,2 %). Les positions réelles disaient **+614,53 $**, donc positif. La
déduction était fausse. Ce script existe pour que la question suivante ne subisse pas
le même sort.

LA QUESTION, TELLE QU'ELLE SE POSE. 5 821 $ de gains réalisés plus 614 $ de latent
font ~6,4 % sur un compte d'environ 100 000 $, quand le tableau de bord affiche le
portefeuille RÉEL à +0,2 %. Ces deux nombres ne se réconcilient pas. Trois causes
possibles, et le script les sépare par la mesure :

1. LE FILTRE `legacy`. `/api/journal` lit `all(legacy=False)` : les fills IMPORTÉS
     (legacy=1, sans features de décision) sont exclus du journal — mais le COMPTE,
     lui, les subit. Si leur P&L est négatif, le journal montre un sous-ensemble
     favorable sans que personne l'ait voulu.
2. LA FENÊTRE. Les aller-retours tombent-ils dans la période couverte par
     `equity_history` ? Sinon on compare un cumul long à un rendement court.
3. LES VERSEMENTS. La courbe du compte est un rendement pondéré dans le temps : deux
     mouvements ont été neutralisés. Le script les affiche.

CE QU'IL NE FAIT PAS : conclure à votre place quand les chiffres ne tranchent pas. Un
résidu inexpliqué est imprimé comme tel.

python scripts/diag_journal_compte.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _jour(ts) -> str:
    return ts.date().isoformat() if hasattr(ts, "date") else str(ts)[:10]


def _bilan(trades: list) -> dict:
    """Réalisé, compte de fermés/ouverts et bornes de dates d'un lot de trades."""
    fermes = [t for t in trades if t.exit_ts]
    ouverts = [t for t in trades if not t.exit_ts]
    dates = sorted(_jour(t.exit_ts) for t in fermes)
    return {"n": len(trades), "n_fermes": len(fermes), "n_ouverts": len(ouverts),
            "realise": round(sum(float(t.pnl_net or 0.0) for t in fermes), 2),
            "gagnants": sum(1 for t in fermes if t.is_win),
            "premier": dates[0] if dates else None,
            "dernier": dates[-1] if dates else None}


def _ligne(nom: str, b: dict) -> None:
    wr = f"{b['gagnants']/b['n_fermes']:.0%}" if b["n_fermes"] else "  —"
    esp = f"{b['realise']/b['n_fermes']:+8.2f}" if b["n_fermes"] else "       —"
    print(f"  {nom:<22} {b['n']:>5} {b['n_fermes']:>7} {b['n_ouverts']:>8} "
          f"{wr:>6} {b['realise']:>11.2f} {esp} "
          f"  {b['premier'] or '—'} → {b['dernier'] or '—'}")


def _journal() -> None:
    from packages.storage import SqliteTradeJournal
    j = SqliteTradeJournal()
    tous = j.all()
    non_legacy = j.all(legacy=False)
    ids = {t.id for t in non_legacy}
    legacy = [t for t in tous if t.id not in ids]
    print("  JOURNAL — ce que le panneau montre, et ce qu'il n'affiche pas\n")
    print(f"  {'périmètre':<22} {'lots':>5} {'fermés':>7} {'ouverts':>8} "
          f"{'win':>6} {'réalisé $':>11} {'esp./tr':>8}   fenêtre des sorties")
    print("  " + "-" * 100)
    b_nl, b_l, b_t = _bilan(non_legacy), _bilan(legacy), _bilan(tous)
    _ligne("legacy=0 (AFFICHÉ)", b_nl)
    _ligne("legacy=1 (MASQUÉ)", b_l)
    _ligne("TOTAL (subi par le compte)", b_t)
    if b_l["n"] == 0:
        print("\n  → Aucun fill legacy. Le filtre n'explique RIEN de l'écart : chercher"
              " ailleurs.")
    else:
        ecart = b_t["realise"] - b_nl["realise"]
        print(f"\n  → Le filtre `legacy` masque {b_l['n']} lots et {ecart:+.2f} $ de "
              "réalisé.")
        if ecart < 0:
            print("    Le journal montre donc un sous-ensemble FAVORABLE — non voulu, "
                  "mais réel.")


def _compte(bilan_total: dict) -> None:
    from packages.execution.equity_history import series
    print("\n  COMPTE — courbe d'equity réelle enregistrée\n")
    trouve = False
    for broker in ("alpaca", "crypto", "binance", "bitmart"):
        pts = series(broker)
        if len(pts) < 2:
            continue
        trouve = True
        v0, v1 = float(pts[0]["v"]), float(pts[-1]["v"])
        print(f"  {broker:<10} {len(pts):>4} points · {pts[0]['t']} → {pts[-1]['t']} · "
              f"{v0:,.2f} $ → {v1:,.2f} $ · variation BRUTE {v1 - v0:+,.2f} $")
        _fenetre(pts, bilan_total)
    if not trouve:
        print("  Aucune courbe enregistrée (equity_history vide) — la comparaison")
        print("  est impossible, et c'est la réponse : rien à réconcilier encore.")


def _fenetre(pts: list, b: dict) -> None:
    """Les sorties du journal tombent-elles DANS la fenêtre de la courbe ?"""
    if not b["premier"]:
        return
    debut, fin = pts[0]["t"], pts[-1]["t"]
    dedans = debut <= b["premier"] and b["dernier"] <= fin
    etat = "DANS la fenêtre" if dedans else "⚠ DÉBORDE la fenêtre de la courbe"
    print(f"    sorties du journal : {b['premier']} → {b['dernier']} · {etat}")
    if not dedans:
        print("    → on compare un cumul de trades à un rendement calculé sur")
        print("      une AUTRE période. À corriger avant toute autre lecture.")


def _residu(b_total: dict, latent: float, variation: float | None) -> None:
    print("\n  RÉCONCILIATION\n")
    print(f"    réalisé (tous lots, legacy compris) : {b_total['realise']:+12,.2f} $")
    print(f"    latent des positions ouvertes       : {latent:+12,.2f} $")
    attendu = b_total["realise"] + latent
    print("    ─────────────────────────────────────────────────")
    print(f"    attendu sur le compte               : {attendu:+12,.2f} $")
    if variation is None:
        print("    variation constatée                 :          n/d")
        print("\n  → Sans courbe d'equity, le résidu ne peut pas être calculé. Rien "
              "n'est conclu.")
        return
    print(f"    variation constatée (brute)         : {variation:+12,.2f} $")
    residu = variation - attendu
    print(f"    RÉSIDU INEXPLIQUÉ                   : {residu:+12,.2f} $")
    print("\n  Le résidu contient les versements/retraits (la courbe brute les inclut, "
          "le\n  P&L non), les frais hors P&L, et tout lot antérieur au journal. Un "
          "résidu\n  proche de zéro signifie que journal et compte racontent la même "
          "histoire.")


def _latent() -> float:
    """Latent RÉEL, lu chez le courtier — jamais estimé à partir d'un prix d'entrée."""
    try:
        from apps.api.snapshot import build_snapshot
        real = (build_snapshot().get("live") or {}).get("real") or {}
        total = 0.0
        for compte in ("alpaca", "crypto"):
            for pos in (real.get(compte) or {}).get("positions", []) or []:
                total += float(pos.get("pnl") or 0.0)
        return round(total, 2)
    except Exception as e:  # noqa: BLE001
        print(f"  (latent indisponible : {str(e)[:60]})")
        return 0.0


def main() -> None:
    print(__doc__.split("    python")[0].rstrip())
    print()
    try:
        from packages.storage import SqliteTradeJournal
        b_total = _bilan(SqliteTradeJournal().all())
    except Exception as e:  # noqa: BLE001
        print(f"Journal illisible : {str(e)[:80]}")
        return
    _journal()
    _compte(b_total)
    print("\n  Construction du snapshot pour lire le latent RÉEL… ~30-60 s")
    latent = _latent()
    from packages.execution.equity_history import series
    variation = None
    for broker in ("alpaca", "crypto", "binance", "bitmart"):
        pts = series(broker)
        if len(pts) >= 2:
            variation = (variation or 0.0) + float(pts[-1]["v"]) - float(pts[0]["v"])
    _residu(b_total, latent, variation)


if __name__ == "__main__":
    main()
