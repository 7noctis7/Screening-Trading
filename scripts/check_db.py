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
         "close": ["close", "adj_close", "adjclose", "adj", "last", "price", "c"],
         "volume": ["volume", "vol", "v"]}
_DATE = ["date", "datetime", "timestamp", "dt", "ts", "time", "day", "period"]
_SYM = ["symbol", "ticker", "sym", "code"]
_LINK = ["ticker_id", "tickerid", "sec_id", "secid", "instrument_id", "id", "ticker", "symbol", "code"]
_META_ID = ["id", "ticker_id", "tickerid", "sec_id", "secid", "rowid"]


def _pick(cols, cands):
    for c in cands:                       # exact
        if c in cols:
            return cols[c]
    for c in cands:                       # sous-chaîne (colonnes préfixées)
        for k, orig in cols.items():
            if c in k:
                return orig
    return None


def _strict_sym(cols):
    for k, orig in cols.items():
        if "symbol" in k:
            return orig
    for c in ("ticker", "sym", "code"):
        if c in cols and not cols[c].lower().startswith("id"):
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

    # --- SCHÉMA DÉTAILLÉ : colonnes + 1 ligne d'exemple (INSTANTANÉ, sans COUNT) ---
    print("\n── SCHÉMA DÉTAILLÉ (colle ceci dans le chat) ──")
    for t in tables:
        cols = [c[1] for c in conn.execute(f'PRAGMA table_info("{t}")')]
        print(f'  TABLE "{t}" : {", ".join(cols)}')
        try:
            sample = conn.execute(f'SELECT * FROM "{t}" LIMIT 1').fetchone()  # LIMIT 1 = instantané
            if sample:
                print(f"      ex: {str(tuple(sample))[:180]}")
        except sqlite3.Error:
            pass
    print("── fin schéma ──\n")

    # détection (même logique que le lecteur du robot) : long / normalisé / per-ticker
    long = norm = None
    for t in tables:
        cl = _columns(conn, t)
        sym = _strict_sym(cl)
        if sym and _pick(cl, _DATE) and _pick(cl, _OHLC["close"]):
            long = (t, sym, _pick(cl, _DATE), {k: _pick(cl, v) for k, v in _OHLC.items()})
            break
    if not long:
        prices = []
        for t in tables:
            cl = _columns(conn, t)
            if _pick(cl, _DATE) and _pick(cl, _OHLC["close"]) and _pick(cl, _LINK):
                prices.append((t, cl, _pick(cl, _DATE), _pick(cl, _LINK)))
        if prices:
            prices.sort(key=lambda p: ("1d" in p[0].lower(),
                                       any(h in p[0].lower() for h in ("daily", "eod", "day"))),
                        reverse=True)
            pt, cl, dat, link = prices[0]
            sym2id, meta = {}, None
            for mt in tables:
                if mt == pt:
                    continue
                mc = _columns(conn, mt); ms = _strict_sym(mc); mid = _pick(mc, _META_ID)
                if ms and mid:
                    sym2id = {str(r[1]).upper(): r[0]
                              for r in conn.execute(f'SELECT "{mid}","{ms}" FROM "{mt}"') if r[1]}
                    meta = mt
                    break
            o = {k: _pick(cl, v) for k, v in _OHLC.items()}
            norm = (pt, link, dat, o, sym2id, meta)
    schema = (f"format LONG ({long[0]})" if long else
              f"normalisé (prix {norm[0]} · lien {norm[1]} · méta {norm[5]} · {len(norm[4])} tickers)"
              if norm else "une table par ticker")
    print(f"   Schéma détecté : {schema}")

    # contrôle d'INDEX (crucial pour la vitesse : sans index, chaque requête scanne tout P_1D)
    if norm:
        idx = [r[1] for r in conn.execute(f'PRAGMA index_list("{norm[0]}")')]
        has = bool(idx)
        print(f"   Index sur {norm[0]} : {'oui' if has else 'AUCUN → lecture lente !'}")
        if not has:
            print(f"      ⚡ Créez-le UNE fois (gros gain de vitesse) :  python3 scripts/index_db.py")

    found = 0
    for s in a.symbols:
        rows = []
        try:
            if long:
                t, sym, dat, o = long
                rows = conn.execute(f'SELECT "{dat}","{o["close"]}" FROM "{t}" WHERE "{sym}"=? '
                                    f'ORDER BY "{dat}" LIMIT 100000', (s,)).fetchall()
            elif norm:
                pt, link, dat, o, sym2id, _ = norm
                lv = sym2id.get(s.upper())
                if lv is not None:
                    rows = conn.execute(f'SELECT "{dat}","{o["close"]}" FROM "{pt}" WHERE "{link}"=? '
                                        f'ORDER BY "{dat}" LIMIT 100000', (lv,)).fetchall()
        except sqlite3.Error:
            rows = []
        if rows:
            found += 1
            print(f"   • {s:14s} {len(rows):>6d} barres  {str(rows[0][0])[:10]} → {str(rows[-1][0])[:10]}"
                  f"  dernier {rows[-1][1]}")
        else:
            print(f"   • {s:14s} (absent)")
    print(f"\n{found}/{len(a.symbols)} symboles trouvés.")
    if found:
        print("✅ Connexion OK : le robot utilisera ces données réelles (mode réel/mixte).")
    print("\n➡️  Base déjà connectée définitivement via ~/.zshrc. Lancez :  make interactive")


if __name__ == "__main__":
    main()
