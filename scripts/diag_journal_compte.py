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


BROKERS = ("alpaca", "crypto", "binance", "bitmart")


def _courbes() -> dict[str, list]:
    """Les courbes lues UNE SEULE FOIS.

    Elles étaient relues après `build_snapshot()`, qui ENREGISTRE le point du jour :
    les deux lectures ne portaient donc pas sur la même série et le total ne
    correspondait plus à la somme des lignes (3,39 $ d'écart le 03/09). Une mesure qui
    ne se recoupe pas avec elle-même ne vaut rien, si petit que soit l'écart.
    """
    from packages.execution.equity_history import series
    return {b: series(b) for b in BROKERS}


def _compte(courbes: dict, bilan_total: dict) -> None:
    print("\n  COMPTE — courbe d'equity réelle enregistrée\n")
    trouve = False
    for broker, pts in courbes.items():
        if len(pts) < 2:
            continue
        trouve = True
        v0, v1 = float(pts[0]["v"]), float(pts[-1]["v"])
        print(f"  {broker:<10} {len(pts):>4} points · {pts[0]['t']} → {pts[-1]['t']} · "
              f"{v0:,.2f} $ → {v1:,.2f} $ · variation BRUTE {v1 - v0:+,.2f} $")
        _fenetre(pts, bilan_total)
        _mouvements(pts)
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


def _mouvements(pts: list, k: float = 6.0) -> None:
    """Sauts journaliers hors norme = versements ou retraits, pas des gains.

    On ne compare pas à un seuil en dollars, qui dépendrait de la taille du compte, mais
    à la dispersion OBSERVÉE de la série : `k` fois l'écart absolu médian. Un compte
    calme rend le filtre plus sensible, un compte agité moins — ce qui est le
    comportement voulu.
    """
    ecarts = [float(pts[i]["v"]) - float(pts[i - 1]["v"]) for i in range(1, len(pts))]
    if len(ecarts) < 5:
        return
    medabs = sorted(abs(x) for x in ecarts)[len(ecarts) // 2]
    seuil = max(k * medabs, 1.0)
    gros = [(pts[i + 1]["t"], e) for i, e in enumerate(ecarts) if abs(e) > seuil]
    if not gros:
        print(f"    aucun mouvement suspect (seuil {seuil:,.2f} $/jour) — "
              "la variation est du P&L")
        return
    total = sum(e for _, e in gros)
    print(f"    {len(gros)} saut(s) hors norme (> {seuil:,.2f} $/jour), total "
          f"{total:+,.2f} $ — candidats VERSEMENT/RETRAIT :")
    for t, e in gros[:6]:
        print(f"      {t}  {e:+,.2f} $")


def _lots_vs_courtier(ouverts: list, positions: dict) -> None:
    """Les lots OUVERTS du journal correspondent-ils aux positions RÉELLES ?

    C'est la mesure qui tranche si le réalisé est surévalué. Le P&L réalisé s'obtient
    en appariant les ventes à des lots ouverts : si le journal porte des lots que le
    courtier ne détient pas, ces appariements produisent des gains qui n'ont jamais
    existé. On compare donc les QUANTITÉS, symbole par symbole, sans rien supposer.
    """
    from packages.research.biais_fermeture import symbole_canonique
    par_sym: dict[str, float] = {}
    for lot in ouverts:
        c = symbole_canonique(lot.instrument)
        par_sym[c] = par_sym.get(c, 0.0) + float(lot.qty or 0)
    positions = {symbole_canonique(k): v for k, v in (positions or {}).items()}
    print("\n  LOTS OUVERTS DU JOURNAL vs POSITIONS RÉELLES\n")
    if not positions:
        print("    positions courtier indisponibles — comparaison impossible, "
              "rien n'est conclu.")
        return
    print(f"    {'symbole':<12} {'journal':>14} {'courtier':>14} {'écart':>14}")
    print("    " + "-" * 58)
    ecart_total = 0.0
    for sym in sorted(set(par_sym) | set(positions)):
        qj, qc = par_sym.get(sym, 0.0), positions.get(sym, 0.0)
        d = qj - qc
        ecart_total += abs(d)
        marque = "  ←" if abs(d) > 1e-6 * max(1.0, abs(qc)) else ""
        print(f"    {sym:<12} {qj:>14.6f} {qc:>14.6f} {d:>+14.6f}{marque}")
    _age_fantomes(ouverts, positions)
    if ecart_total < 1e-6:
        print("\n    → Journal et courtier sont d'accord. Le réalisé n'est PAS gonflé "
              "par des lots fantômes : chercher le résidu ailleurs.")
    else:
        print("\n    → ÉCART. Le journal porte des quantités que le courtier ne "
              "confirme pas.\n      Les ventes appariées à ces lots produisent un "
              "réalisé sans contrepartie réelle.")


def _age_fantomes(ouverts: list, positions: dict) -> None:
    """Depuis QUAND les lots que le courtier ne détient plus sont-ils « ouverts » ?

    C'est le dernier maillon. Si ces lots datent d'avant un réaménagement du
    portefeuille, la conclusion est mécanique : les ventes qui les ont soldés n'ont
    jamais été enregistrées, donc ils restent ouverts pour toujours — et les ventes
    RÉCENTES viennent s'apparier à eux en FIFO, produisant un réalisé calculé sur un
    prix de revient qui n'a plus rien à voir avec le compte.
    """
    from packages.research.biais_fermeture import symbole_canonique
    detenus = {symbole_canonique(k) for k, v in (positions or {}).items() if v}
    fantomes = [t for t in ouverts if symbole_canonique(t.instrument) not in detenus]
    if not fantomes:
        return
    dates = sorted(_jour(t.entry_ts) for t in fantomes)
    print(f"\n    {len(fantomes)} lots ouverts sur des titres que le courtier ne "
          f"détient PLUS\n    entrés entre {dates[0]} et {dates[-1]} — les ventes qui "
          "les ont soldés\n    n'ont jamais été journalisées, donc ils ne se "
          "fermeront jamais.")


def _positions_courtier() -> dict:
    """Quantités RÉELLEMENT détenues par symbole, telles que le courtier les dit."""
    try:
        from apps.api.snapshot import build_snapshot
        real = (build_snapshot().get("live") or {}).get("real") or {}
        out: dict[str, float] = {}
        for compte in ("alpaca", "crypto"):
            for pos in (real.get(compte) or {}).get("positions", []) or []:
                if pos.get("symbol"):
                    out[pos["symbol"]] = float(pos.get("qty") or 0.0)
        return out
    except Exception as e:  # noqa: BLE001
        print(f"  (positions courtier indisponibles : {str(e)[:60]})")
        return {}


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
        j = SqliteTradeJournal()
        tous = j.all()
        b_total = _bilan(tous)
    except Exception as e:  # noqa: BLE001
        print(f"Journal illisible : {str(e)[:80]}")
        return
    _journal()
    # La courbe est lue AVANT le snapshot : `build_snapshot` enregistre le point du jour
    # et modifierait la série entre deux lectures.
    courbes = _courbes()
    _compte(courbes, b_total)
    print("\n  Construction du snapshot pour lire le courtier… ~30-60 s")
    positions = _positions_courtier()
    _lots_vs_courtier([t for t in tous if not t.exit_ts], positions)
    latent = _latent()
    variation = None
    for pts in courbes.values():
        if len(pts) >= 2:
            variation = (variation or 0.0) + float(pts[-1]["v"]) - float(pts[0]["v"])
    _residu(b_total, latent, variation)


if __name__ == "__main__":
    main()
