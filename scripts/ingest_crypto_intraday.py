#!/usr/bin/env python3
"""Ingestion OHLCV CRYPTO 1h / 4h depuis Binance → `data/crypto_intraday.db`.

POURQUOI LA CRYPTO D'ABORD (18/09). Le dépôt n'a que du QUOTIDIEN, et la jambe
d'exécution intraday de plusieurs specs reste UNCALIBRATED (`vault/03_TODO.md`).
Côté actions, l'histoire intraday gratuite est bridée — yfinance plafonne le 1h à
~730 jours, et le palier gratuit d'Alpaca sert le flux IEX, dont les VOLUMES ne
représentent pas le marché (or nos détecteurs filtrent sur le volume). Côté crypto,
Binance sert 1h et 4h gratuitement, sans clé, sur tout l'historique de la paire.

C'est donc le seul endroit où l'on peut MESURER si l'intraday apporte quelque chose
sans payer ni dépendre d'une source partielle. Si l'apport n'existe pas là où les
données sont complètes, il n'existera pas sur deux ans d'IEX.

UNE BASE SIDECAR, JAMAIS `crypto.db`. La base quotidienne est lue par la production ; y
mêler des barres horaires ferait varier le nombre de lignes par jour sans prévenir. Le
schéma de `bars_repo` porte pourtant (symbol, timeframe, ts) en clé : la séparation est
une prudence d'exploitation, pas une limite technique.

CE QUE CE SCRIPT N'ÉCRIT PAS. La bougie EN COURS — `crypto_binance` l'écarte sur
son `closeTime`, parce que son plus-haut et sa clôture bougent encore. En quotidien
le défaut passait presque inaperçu ; en 1h il serait permanent.

    python scripts/ingest_crypto_intraday.py                    # 1h + 4h, univers
    python scripts/ingest_crypto_intraday.py --tf 1h --top 10
    python scripts/ingest_crypto_intraday.py --depuis 2020-01-01
"""
from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BASE = ROOT / "data" / "crypto_intraday.db"
TIMEFRAMES = ("1h", "4h")


def _barres(base: str, tf: str, lignes: list) -> list:
    """Tuples Binance → `Bar`. Une ligne illisible est SAUTÉE, jamais devinée."""
    from packages.core.models import Bar
    out = []
    for ts, o, h, b, c, v in lignes:
        try:
            quand = datetime.fromisoformat(ts)
        except ValueError:
            continue
        out.append(Bar(f"{base}/USDT", tf,
                       quand if quand.tzinfo else quand.replace(tzinfo=UTC),
                       float(o), float(h), float(b), float(c), float(v)))
    return out


def _depuis(repo, base: str, tf: str, defaut: str) -> str:
    """Reprise INCRÉMENTALE : on repart de la dernière barre connue, sinon du défaut.

    Sans cela, chaque passage rejouerait tout l'historique — des dizaines de milliers
    d'appels pour quelques barres neuves, et un rate-limit garanti.
    """
    dernier = repo.last_ts(f"{base}/USDT", tf)
    return dernier.isoformat() if dernier else defaut


def _ingerer(repo, bases: list[str], tf: str, defaut: str, verbeux: bool) -> dict:
    from packages.data.crypto_binance import historique
    total, muets = 0, []
    for base in bases:
        lignes = historique(base, depuis=_depuis(repo, base, tf, defaut), interval=tf)
        barres = _barres(base, tf, lignes)
        if not barres:
            muets.append(base)
            continue
        total += repo.upsert(barres)
        if verbeux:
            print(f"    {base:<8} {tf}  {len(barres):>6} barres  "
                  f"{barres[0].ts.date()} → {barres[-1].ts.date()}")
    return {"ecrites": total, "muets": muets}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", nargs="*", default=list(TIMEFRAMES),
                    help="timeframes à ingérer (1h, 4h)")
    ap.add_argument("--top", type=int, default=0, help="0 = tout l'univers crypto")
    ap.add_argument("--depuis", default="2017-01-01")
    ap.add_argument("--silencieux", action="store_true")
    a = ap.parse_args()

    print(__doc__.split("    python")[0].rstrip())
    inconnus = [t for t in a.tf if t not in TIMEFRAMES]
    if inconnus:
        print(f"\n  ✗ timeframe(s) non géré(s) : {inconnus} — connus : {TIMEFRAMES}")
        return 2

    from packages.storage.bars_repo import SqliteBarsRepository
    from scripts.ingest_crypto import _bases_univers
    bases = _bases_univers(a.top)
    if not bases:
        print("\n  ⚠ aucune base crypto dans l'univers — rien à ingérer.")
        return 2

    BASE.parent.mkdir(parents=True, exist_ok=True)
    repo = SqliteBarsRepository(BASE)
    print(f"\n  {len(bases)} base(s) crypto · timeframes {a.tf} · depuis {a.depuis}")
    print(f"  Destination : {BASE.relative_to(ROOT)}\n")
    try:
        for tf in a.tf:
            r = _ingerer(repo, bases, tf, a.depuis, not a.silencieux)
            print(f"\n  {tf} : {r['ecrites']} ligne(s) écrite(s)")
            if r["muets"]:
                # UNE SOURCE MUETTE SE NOMME. Une paire absente de Binance n'est pas une
                # erreur, mais la taire laisserait croire l'univers complet.
                print(f"       {len(r['muets'])} base(s) sans données : "
                      + ", ".join(r["muets"][:12])
                      + ("…" if len(r["muets"]) > 12 else ""))
        print(f"\n  Total en base : {repo.count()} barre(s).")
        print("  Mesurer ensuite :  make deviation-lab-crypto\n")
    finally:
        repo.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
