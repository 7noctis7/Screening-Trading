"""Diagnostic AUTONOME de votre base de prix (YAHOO.db) — à lancer SUR VOTRE MAC.

Ne dépend QUE de la librairie standard Python (sqlite3) : pas besoin d'installer le projet.
Il LOCALISE la base, vérifie qu'elle est lisible, affiche le schéma, des symboles d'exemple,
le nb de barres et la plage de dates, puis indique comment la connecter DÉFINITIVEMENT.

  python3 scripts/check_db.py
  python3 scripts/check_db.py --symbols AAPL NVDA PLTR BTC/USDC
  QUANT_PRICE_DB=~/Desktop/YAHOO.db python3 scripts/check_db.py
"""

from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path

_OHLC = {"open": ["open", "o"], "high": ["high", "h"], "low": ["low", "l"],
         "close": ["close", "adj_close", "adjclose", "c"], "volume": ["volume", "vol", "v"]}
_DATE = ["date", "datetime", "timestamp", "ts", "day"]
_SYM = ["symbol", "ticker", "sym", "code"]


def _pick(cols, cands):
    for c in cands:
        if c in cols:
            return cols[c]
    return None


def _find_db() -> Path | None:
    """Cherche QUANT_PRICE_DB puis les emplacements usuels, sinon scanne le dossier perso."""
    env = os.environ.get("QUANT_PRICE_DB")
    if env and Path(env).expanduser().exists():
        return Path(env).expanduser()
    home = Path.home()
    usual = [Path("data/YAHOO.db"), Path("data/market.db"),
             home / "Desktop" / "YAHOO.db", home / "Bureau" / "YAHOO.db",
             home / "Documents" / "YAHOO.db", home / "Downloads" / "YAHOO.db",
             home / "Library/Mobile Documents/com~apple~CloudDocs/Desktop/YAHOO.db"]
    for p in usual:
        if p.exists():
            return p
    # scan large (profondeur limitée) pour retrouver n'importe quel *.db nommé yahoo
    hits = []
    for base in (home / "Desktop", home / "Documents", home / "Downloads", home):
        if not base.exists():
            continue
        for p in base.rglob("*.db"):
            if "yahoo" in p.name.lower():
                hits.append(p)
        if hits:
            break
    if hits:
        print("ℹ️  Bases candidates trouvées par recherche :")
        for h in hits[:8]:
            print(f"     {h}  ({h.stat().st_size/1e6:,.0f} Mo)")
        return hits[0]
    return None


def _columns(conn, table):
    return {r[1].lower(): r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="*", default=["AAPL", "NVDA", "PLTR", "MSFT", "BTC/USDC"])
    a = ap.parse_args()

    db = _find_db()
    if db is None:
        print("❌ Base introuvable. Localisez-la puis pointez-la :")
        print("   mdfind -name YAHOO.db            # Spotlight : affiche le chemin exact")
        print("   export QUANT_PRICE_DB=/chemin/vers/YAHOO.db")
        return
    print(f"✅ Base : {db}  ({db.stat().st_size/1e6:,.0f} Mo)")
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    print(f"   Tables : {len(tables)} → {', '.join(tables[:10])}{' …' if len(tables) > 10 else ''}")

    # --- SCHÉMA DÉTAILLÉ : colonnes + 1 ligne d'exemple par table (pour adapter le lecteur) ---
    print("\n── SCHÉMA DÉTAILLÉ (colle ceci dans le chat) ──")
    for t in tables:
        cols = [c[1] for c in conn.execute(f'PRAGMA table_info("{t}")')]
        try:
            nrows = conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        except sqlite3.Error:
            nrows = "?"
        print(f'  TABLE "{t}" ({nrows} lignes) : {", ".join(cols)}')
        try:
            sample = conn.execute(f'SELECT * FROM "{t}" LIMIT 1').fetchone()
            if sample:
                print(f"      ex: {str(sample)[:160]}")
        except sqlite3.Error:
            pass
    print("── fin schéma ──\n")

    # format long (table avec colonne symbole) ?
    long = None
    for t in tables:
        cl = _columns(conn, t)
        if _pick(cl, _SYM) and _pick(cl, _DATE) and _pick(cl, _OHLC["close"]):
            long = (t, _pick(cl, _SYM), _pick(cl, _DATE),
                    {k: _pick(cl, v) for k, v in _OHLC.items()})
            break
    print(f"   Schéma : {'format LONG (table ' + long[0] + ')' if long else 'une table par ticker'}")

    found = 0
    for s in a.symbols:
        rows = []
        try:
            if long:
                t, sym, dat, o = long
                rows = conn.execute(
                    f'SELECT "{dat}","{o["close"]}" FROM "{t}" WHERE "{sym}"=? ORDER BY "{dat}"',
                    (s,)).fetchall()
            elif s in tables:
                cl = _columns(conn, s); dat = _pick(cl, _DATE); c = _pick(cl, _OHLC["close"])
                if dat and c:
                    rows = conn.execute(f'SELECT "{dat}","{c}" FROM "{s}" ORDER BY "{dat}"').fetchall()
        except sqlite3.Error:
            rows = []
        if rows:
            found += 1
            print(f"   • {s:14s} {len(rows):>6d} barres  {str(rows[0][0])[:10]} → {str(rows[-1][0])[:10]}"
                  f"  dernier {rows[-1][1]}")
        else:
            print(f"   • {s:14s} (absent)")
    print(f"\n{found}/{len(a.symbols)} symboles trouvés.")
    print("\n➡️  Pour connecter DÉFINITIVEMENT cette base (zsh) :")
    print(f'   echo \'export QUANT_PRICE_DB="{db}"\' >> ~/.zshrc && source ~/.zshrc')
    print("   puis :  make api   (ou)   python3 apps/web/preview/build_interactive.py")


if __name__ == "__main__":
    main()
