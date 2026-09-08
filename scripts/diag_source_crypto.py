"""Pourquoi telle série crypto est-elle inexploitable ? On mesure, on ne suppose pas.

  python scripts/diag_source_crypto.py                  # tout l'univers crypto
  python scripts/diag_source_crypto.py --symboles UNI ARB OP STX TON SHIB

CE QUI A DÉCLENCHÉ CE SCRIPT. L'audit croisé du 08/09 a trouvé 5 séries cassées et 7
figées — TOUTES des paires `/USDC` (UNI, ARB, OP, STX, TON ; SHIB immobile 675 séances
sur 1499, ARB 595). Douze séries sur un même format de symbole, ce n'est pas le hasard
du marché : c'est la source. Restait à savoir LAQUELLE des causes possibles, parce
qu'elles appellent des gestes opposés.

LES QUATRE CAUSES POSSIBLES, ET COMMENT ON LES SÉPARE.

  · COLLISION DE TICKER — `UNI/USDC` est ingéré en interrogeant `UNI-USD` chez Yahoo.
    Si ce symbole court est occupé par un homonyme illiquide, la base contient la série
    d'un AUTRE jeton : elle est propre de forme, et fausse de bout en bout. Signature :
    les rendements ne corrèlent pas avec la référence. Geste : forcer le bon ticker.
  · FLUX ARRÊTÉ — la source a cessé de coter. Signature : longue plage de clôtures
    identiques. Geste : retirer la série jusqu'à réparation.
  · PRÉCISION — un jeton à 0,00001 $ arrondi à six décimales ne bouge plus qu'en
    marches d'escalier. Signature : très peu de clôtures distinctes. Geste : changer la
    source, pas le seuil.
  · CONFORME — la série suit la référence : l'anomalie est réelle, pas une avarie.

LA RÉFÉRENCE. Binance klines (gratuit, sans clé, déjà utilisé pour le funding et le prix
BTC). Sans réseau, le script le DIT et rend « non vérifiable » — il n'invente pas de
verdict, ce qui serait exactement le piège du mandat données-réelles.

Ce script ne corrige RIEN. Il imprime, pour chaque série fautive, la ligne exacte à
ajouter à `ALIAS_YAHOO` dans scripts/ingest_crypto.py. L'écriture reste un geste humain.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CORR_MIN = 0.50            # sous ce niveau, deux séries ne décrivent pas le même
                           # actif
JOURS_COMMUNS_MIN = 100    # sous ce nombre, la corrélation ne vaut rien
FIGE_MIN = 20              # plage de clôtures identiques : au-delà, on parle d'arrêt
DISTINCTES_MIN = 0.50      # part de clôtures distinctes : en dessous, on suspecte
                           # un arrondi destructeur


def _bases_univers() -> list[str]:
    from scripts.ingest_crypto import _bases_univers
    return _bases_univers(10_000)


def lire_base(db: Path, ticker: str) -> list[tuple[str, float]]:
    """[(date, clôture)] trié, depuis crypto.db.

    Liste vide si la base, la table ou le symbole manque — un poste sans crypto.db ne
    doit pas faire échouer le diagnostic, seulement le rendre muet."""
    if not db.exists():
        return []
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=30)
    try:
        rows = conn.execute(
            "SELECT date, close FROM prices WHERE symbol=? ORDER BY date",
            (ticker,)).fetchall()
    except sqlite3.Error:
        return []
    finally:
        conn.close()
    return [(str(d), float(c)) for d, c in rows if c is not None and float(c) > 0]


def reference_binance(base: str, limite: int = 1000) -> list[tuple[str, float]]:
    """Clôtures quotidiennes de `{base}USDT` chez Binance. [] si indisponible."""
    from packages.data.crypto_history import _get_json, parse_klines
    url = ("https://api.binance.com/api/v3/klines"
           f"?symbol={base.upper()}USDT&interval=1d&limit={int(limite)}")
    return parse_klines(_get_json(url))


def _plus_longue_plage_figee(closes: list[float]) -> int:
    """Plus longue suite de clôtures strictement identiques."""
    pire = courante = 1
    for a, b in zip(closes, closes[1:], strict=False):
        courante = courante + 1 if a == b else 1
        pire = max(pire, courante)
    return pire if closes else 0


def _correlation(x: list[float], y: list[float]) -> float:
    import numpy as np
    a, b = np.asarray(x, float), np.asarray(y, float)
    if a.size < 2 or a.std() == 0 or b.std() == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def _rendements_alignes(
        serie: list[tuple[str, float]],
        ref: list[tuple[str, float]]) -> tuple[list[float], list[float]]:
    """Rendements quotidiens sur les dates COMMUNES aux deux séries."""
    d_ref = dict(ref)
    communes = sorted(d for d, _ in serie if d in d_ref)
    d_ser = dict(serie)
    ra, rb = [], []
    for veille, jour in zip(communes, communes[1:], strict=False):
        for source, sortie in ((d_ser, ra), (d_ref, rb)):
            sortie.append(source[jour] / source[veille] - 1.0)
    return ra, rb


def diagnostiquer(base: str, serie: list[tuple[str, float]],
                  ref: list[tuple[str, float]]) -> dict:
    """Verdict mesuré pour une base. Aucune cause n'est retenue sans son chiffre."""
    closes = [c for _, c in serie]
    fiche = {"base": base, "barres": len(serie),
             "plage": f"{serie[0][0]}→{serie[-1][0]}" if serie else "—",
             "figee": _plus_longue_plage_figee(closes),
             "distinctes": len(set(closes)) / len(closes) if closes else 0.0,
             "corr": float("nan"), "communes": 0}
    fiche["collision"] = False
    if len(serie) < 250:
        fiche["verdict"] = "SOURCE ABSENTE"
        return fiche
    ra, rb = _rendements_alignes(serie, ref) if ref else ([], [])
    fiche["communes"] = len(ra)
    if len(ra) >= JOURS_COMMUNS_MIN:
        fiche["corr"] = _correlation(ra, rb)
    # Une corrélation basse est un fait à part : elle dit que la base ne décrit PAS
    # l'actif attendu, qu'elle soit figée par ailleurs ou non. Un homonyme illiquide
    # coche souvent les deux cases, et les deux gestes sont à faire.
    mesurable = fiche["corr"] == fiche["corr"]          # NaN ≠ NaN : pas de référence
    fiche["collision"] = bool(mesurable and fiche["corr"] < CORR_MIN)
    # L'ordre va du fait le plus concret au plus interprété : une plage figée et un
    # arrondi se lisent sur la série seule, la corrélation dépend d'une référence.
    if fiche["figee"] >= FIGE_MIN:
        fiche["verdict"] = "FLUX ARRÊTÉ"
    elif fiche["distinctes"] < DISTINCTES_MIN:
        fiche["verdict"] = "PRÉCISION"
    elif fiche["collision"]:
        fiche["verdict"] = "COLLISION DE TICKER"
    elif fiche["communes"] < JOURS_COMMUNS_MIN:
        fiche["verdict"] = "NON VÉRIFIABLE"
    else:
        fiche["verdict"] = "CONFORME"
    return fiche


def _imprimer(fiche: dict, ticker: str) -> None:
    corr = "—" if fiche["corr"] != fiche["corr"] else f"{fiche['corr']:+.2f}"
    print(f"  {fiche['base']:8s} {ticker:14s} {fiche['barres']:5d} barres  "
          f"{fiche['plage']:24s} figée {fiche['figee']:4d}  "
          f"distinctes {100 * fiche['distinctes']:3.0f}%  corr {corr:>5s}  "
          f"→ {fiche['verdict']}")


def _conclure(fiches: list[dict]) -> None:
    collisions = [f for f in fiches if f.get("collision")]
    if collisions:
        print("\n  COLLISION DE TICKER — la base contient la série d'un AUTRE jeton.")
        print("  Trouver le vrai ticker Yahoo (souvent suffixé d'un numéro :")
        print("  ARB11841-USD plutôt que ARB-USD), puis l'inscrire dans ALIAS_YAHOO")
        print("  de scripts/ingest_crypto.py :")
        for f in collisions:
            print(f'      "{f["base"]}": "{f["base"]}<numéro>-USD",   '
                  f'# corr {f["corr"]:+.2f} sur {f["communes"]} jours')
        print("  Puis réingérer : make ingest-crypto ARGS=\"--top 100\"")
    gestes = (
        ("FLUX ARRÊTÉ", "retirer de l'univers jusqu'à réparation de la source"),
        ("PRÉCISION", "changer de source : l'arrondi est dans la donnée"),
        ("SOURCE ABSENTE", "aucune donnée en base — vérifier l'ingestion"),
    )
    for verdict, geste in gestes:
        lot = [f["base"] for f in fiches if f["verdict"] == verdict]
        if lot:
            print(f"\n  {verdict} — {', '.join(lot)}\n      → {geste}")
    if not any(f["verdict"] != "CONFORME" for f in fiches):
        print("\n  ✓ toutes les séries examinées suivent la référence.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Diagnostic des séries crypto en base.")
    ap.add_argument("--symboles", nargs="*",
                    help="bases à examiner (défaut : tout l'univers crypto)")
    ap.add_argument("--sans-reseau", action="store_true",
                    help="n'interroge aucune référence (verdicts partiels)")
    a = ap.parse_args()

    from scripts.ingest_crypto import ticker_yahoo
    bases = [s.upper() for s in (a.symboles or _bases_univers())]
    db = ROOT / "data" / "crypto.db"
    print(f"\nBase : {db}  ({'présente' if db.exists() else 'ABSENTE'})")
    source = "aucune (--sans-reseau)" if a.sans_reseau else "Binance klines"
    print(f"Référence : {source}")
    print(f"{len(bases)} base(s) à examiner\n")

    fiches = []
    for base in bases:
        ticker = ticker_yahoo(base)
        serie = lire_base(db, ticker)
        ref = [] if a.sans_reseau else reference_binance(base)
        fiche = diagnostiquer(base, serie, ref)
        fiches.append(fiche)
        _imprimer(fiche, ticker)
    _conclure(fiches)


if __name__ == "__main__":
    main()
