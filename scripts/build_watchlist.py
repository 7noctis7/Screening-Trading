#!/usr/bin/env python3
"""Watchlist & univers mobile — best practice.

À lancer en LOCAL (données réelles complètes). Produit :
  1) `config/mobile_universe.csv` : les 200 meilleures sociétés par note + une WATCHLIST toujours
     incluse (PLTR, TSLA, BMNR, CLSK, SBET, ABCL, SPCX + cryptos BTC/ETH/ONDO/NEAR/RENDER-USD).
     → ce fichier borne l'univers de la version EN LIGNE/MOBILE (PWA) ; en local tu restes illimité.
  2) `vault/04_Companies/_TOP200.md` : rapport classé (note, secteur, ⭐ watchlist) dans Obsidian.
  3) notes d'analyse Markdown des valeurs de la WATCHLIST dans `vault/04_Companies/`.

    python scripts/build_watchlist.py            # top 200 + watchlist
    python scripts/build_watchlist.py --top 150
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# WATCHLIST TOUJOURS INCLUSE (crypto au format yfinance « -USD »).
WATCHLIST: list[dict] = [
    {"symbol": "PLTR", "name": "Palantir Technologies", "asset_class": "equity"},
    {"symbol": "TSLA", "name": "Tesla", "asset_class": "equity"},
    {"symbol": "BMNR", "name": "Bitmine Immersion", "asset_class": "equity"},
    {"symbol": "CLSK", "name": "CleanSpark", "asset_class": "equity"},
    {"symbol": "SBET", "name": "SharpLink Gaming", "asset_class": "equity"},
    {"symbol": "ABCL", "name": "AbCellera Biologics", "asset_class": "equity"},
    {"symbol": "SPCX", "name": "SPAC / SpaceX proxy", "asset_class": "equity"},
    {"symbol": "BTC-USD", "name": "Bitcoin", "asset_class": "crypto"},
    {"symbol": "ETH-USD", "name": "Ethereum", "asset_class": "crypto"},
    {"symbol": "ONDO-USD", "name": "Ondo", "asset_class": "crypto"},
    {"symbol": "NEAR-USD", "name": "NEAR Protocol", "asset_class": "crypto"},
    {"symbol": "RENDER-USD", "name": "Render", "asset_class": "crypto"},
]


def main() -> int:
    ap = argparse.ArgumentParser(description="Watchlist + univers mobile (top N par note + liste fixe)")
    ap.add_argument("--top", type=int, default=200, help="nombre de meilleures sociétés par note")
    args = ap.parse_args()

    from apps.api.snapshot import build_snapshot
    print("Construction du snapshot (données réelles si QUANT_PRICE_DB branché)…")
    snap = build_snapshot()
    rows = (snap.get("fundamentals", {}) or {}).get("rows", []) or []
    ranked = sorted(rows, key=lambda r: -(r.get("score") or 0))[: args.top]
    by_sym = {r["symbol"]: r for r in rows}

    # univers mobile = top N (∪) watchlist (toujours), dédupliqué, watchlist en tête
    uni: dict[str, dict] = {}
    for w in WATCHLIST:
        r = by_sym.get(w["symbol"], {})
        uni[w["symbol"]] = {"symbol": w["symbol"], "name": r.get("name") or w["name"],
                            "asset_class": w["asset_class"], "venue": "", "currency": "USD",
                            "sector": r.get("sector", ""), "star": True,
                            "score": r.get("score")}
    for r in ranked:
        s = r["symbol"]
        uni.setdefault(s, {"symbol": s, "name": r.get("name", ""), "asset_class": "equity",
                           "venue": "", "currency": "", "sector": r.get("sector", ""),
                           "star": False, "score": r.get("score")})

    # 1) CSV univers mobile (consommé par la PWA en ligne via QUANT_UNIVERSE)
    cfg = ROOT / "config" / "mobile_universe.csv"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    with cfg.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["symbol", "name", "asset_class", "venue", "currency", "sector"])
        for d in uni.values():
            w.writerow([d["symbol"], d["name"], d["asset_class"], d["venue"], d["currency"], d["sector"]])
    print(f"✅ {cfg} — {len(uni)} actifs ({len(WATCHLIST)} watchlist + top {args.top}).")

    # 2) rapport Obsidian classé
    vault = Path(os.environ.get("QUANT_VAULT", ROOT / "vault")) / "04_Companies"
    vault.mkdir(parents=True, exist_ok=True)
    dt = date.today().isoformat()
    lines = ["---", "type: watchlist_top200", f"date: {dt}", f"count: {len(uni)}",
             "tags: [quant, watchlist]", "---", "",
             f"# ⭐ Watchlist & Top {args.top} — {dt}", "",
             "> Univers de la version **mobile/en ligne** (PWA). ⭐ = toujours suivi.", "",
             "| # | Actif | Secteur | Note | ⭐ |", "|--:|---|---|--:|:--:|"]
    star_rows = [d for d in uni.values() if d.get("star")]
    top_rows = [d for d in uni.values() if not d.get("star")][: args.top]
    for i, d in enumerate(star_rows + top_rows, 1):
        sc = "—" if d.get("score") is None else f"{d['score']:.0f}"
        lines.append(f"| {i} | [[{d['symbol']}]] | {d.get('sector','')} | {sc} | {'⭐' if d.get('star') else ''} |")
    lines += ["", f"<small>Généré le {dt} · note = score fondamental composite (value+quality).</small>"]
    (vault / "_TOP200.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ {vault/'_TOP200.md'} — rapport classé Obsidian.")

    # 3) notes d'analyse Markdown des valeurs de la WATCHLIST
    try:
        from apps.api.snapshot import fetch_financials_chain
        from packages.reporting import build_company_report, company_report_markdown
        ok = 0
        for w in WATCHLIST:
            try:
                fin, prior, _ = fetch_financials_chain(w["symbol"])
                if fin is None:
                    continue
                rep = build_company_report(fin, name=w["name"], prior=prior)
                (vault / f"{w['symbol'].replace('/', '_')}.md").write_text(
                    company_report_markdown(rep), encoding="utf-8")
                ok += 1
            except Exception:  # noqa: BLE001
                continue
        print(f"✅ {ok}/{len(WATCHLIST)} notes watchlist écrites dans le coffre.")
    except Exception as e:  # noqa: BLE001
        print(f"(notes watchlist ignorées : {e})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
