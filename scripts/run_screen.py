"""make screen — affiche le screener à FILTRES (packages.screening) sur l'univers courant.

Réutilise le snapshot (source de vérité unique : mêmes données que l'API et le site) et imprime
les candidats éligibles triés par composite z-score. Hors-ligne par défaut (données synthétiques
si aucune base de prix), réel si `.env`/DB présents.
"""

from __future__ import annotations


def main() -> int:
    from apps.api.snapshot import build_snapshot

    sec = build_snapshot().get("screen", {})
    if not sec.get("available"):
        print("Screener indisponible :", sec.get("error", "—"))
        return 1

    filters = ", ".join(sec.get("filters", []))
    print(f"\nScreener — {sec['count']} candidats / {sec['universe_size']} de l'univers")
    print(f"Filtres : {filters}\n")
    print(f"{'#':>3}  {'Symbole':<14} {'Score':>7} {'Ret12m':>8} {'Drawdown':>9}  Secteur")
    print("-" * 70)
    for r in sec.get("rows", []):
        ret = (r.get("ret_12m") or 0.0) * 100
        dd = (r.get("drawdown") or 0.0) * 100
        print(f"{r['rank']:>3}  {r['symbol']:<14} {r.get('score', 0):>7.2f} "
              f"{ret:>7.1f}% {dd:>8.1f}%  {r.get('sector', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
