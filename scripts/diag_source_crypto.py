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
RETARD_MAX = 30            # jours de retard sur la série la plus fraîche du lot


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


def reference_binance(base: str, depuis: str = "2015-01-01") -> list[tuple[str, float]]:
    """Clôtures quotidiennes de `{base}USDT` chez Binance. [] si indisponible.

    Historique PAGINÉ depuis 2015. La première version demandait les 1000 dernières
    barres : toute série qui s'arrête avant fin 2023 n'avait alors aucun recouvrement
    avec la référence, et sortait « NON VÉRIFIABLE » — soit dix séries du premier
    passage réel, dont COMP, GMX, IMX et GRT — précisément les plus suspectes, puisque
    ce sont celles qui s'arrêtent des années trop tôt. Le trou de la mesure tombait
    exactement sur ses propres cibles.
    """
    from packages.data.crypto_binance import historique
    return [(jour, close) for jour, _o, _h, _b, close, _v in historique(base, depuis)]


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


def _jours_de_retard(fin: str, reference: str | None) -> int:
    """Écart en jours entre la dernière barre d'une série et la plus fraîche du lot."""
    if not reference or not fin:
        return 0
    from datetime import date
    return max(0, (date.fromisoformat(reference) - date.fromisoformat(fin)).days)


def diagnostiquer(base: str, serie: list[tuple[str, float]],
                  ref: list[tuple[str, float]],
                  dernier_jour: str | None = None) -> dict:
    """Verdict mesuré pour une base. Aucune cause n'est retenue sans son chiffre."""
    closes = [c for _, c in serie]
    fiche = {"base": base, "barres": len(serie),
             "plage": f"{serie[0][0]}→{serie[-1][0]}" if serie else "—",
             "figee": _plus_longue_plage_figee(closes),
             "distinctes": len(set(closes)) / len(closes) if closes else 0.0,
             "corr": float("nan"), "communes": 0,
             "retard": _jours_de_retard(serie[-1][0] if serie else "", dernier_jour)}
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
    # ORDRE CORRIGÉ SUR DONNÉES RÉELLES (09/09). J'avais mis la plage figée en premier,
    # au motif qu'elle se lit sur la série seule. Le premier passage réel a montré que
    # c'était l'ordre qui trompe : UNI et ARB, corrélation +0,25 et +0,04, sortaient
    # « FLUX ARRÊTÉ » alors que leur immobilité est un SYMPTÔME — celle de l'homonyme
    # illiquide que la base contient à leur place. Le geste juste est de changer de
    # source, pas de retirer la série. Une corrélation quasi nulle invalide tout le
    # reste de ce qu'on peut dire d'une série : elle passe donc en tête. Puis l'arrondi,
    # qui FABRIQUE des plages figées (SHIB : corr +0,80, donc le bon jeton, mais 3 % de
    # clôtures distinctes). La plage figée ne reste une cause qu'une fois les deux
    # autres écartées.
    if fiche["collision"]:
        fiche["verdict"] = "COLLISION DE TICKER"
    elif fiche["distinctes"] < DISTINCTES_MIN:
        fiche["verdict"] = "PRÉCISION"
    elif fiche["figee"] >= FIGE_MIN:
        fiche["verdict"] = "FLUX ARRÊTÉ"
    elif fiche["retard"] > RETARD_MAX:
        # Une série qui s'arrête des années avant les autres n'est pas « conforme » :
        # le jeton a migré, été délisté, ou la source l'a lâchée. Elle traîne dans
        # l'univers en se faisant passer pour vivante.
        fiche["verdict"] = "PÉRIMÉE"
    elif fiche["communes"] < JOURS_COMMUNS_MIN:
        fiche["verdict"] = "NON VÉRIFIABLE"
    else:
        fiche["verdict"] = "CONFORME"
    return fiche


def _imprimer(fiche: dict, ticker: str) -> None:
    corr = "—" if fiche["corr"] != fiche["corr"] else f"{fiche['corr']:+.2f}"
    retard = f"{fiche['retard']:4d} j" if fiche.get("retard") else "    —"
    print(f"  {fiche['base']:8s} {ticker:14s} {fiche['barres']:5d} barres  "
          f"{fiche['plage']:24s} figée {fiche['figee']:4d}  "
          f"distinctes {100 * fiche['distinctes']:3.0f}%  corr {corr:>5s}  "
          f"retard {retard}  → {fiche['verdict']}")


def _conclure(fiches: list[dict]) -> None:
    collisions = [f for f in fiches if f.get("collision")]
    if collisions:
        print("\n  COLLISION DE TICKER — la base contient la série d'un AUTRE jeton.")
        print("  Plutôt que de chercher le bon symbole Yahoo, forcer la source sur")
        print("  celle contre laquelle la mesure a été faite. Dans SOURCE_FORCEE")
        print("  de scripts/ingest_crypto.py :")
        for f in collisions:
            print(f'      "{f["base"]}": "binance",   '
                  f'# corr {f["corr"]:+.2f} sur {f["communes"]} jours')
        print("  Puis réingérer : make ingest-crypto")
    gestes = (
        ("FLUX ARRÊTÉ", "retirer de l'univers jusqu'à réparation de la source"),
        ("PRÉCISION", "changer de source : l'arrondi est dans la donnée"),
        ("SOURCE ABSENTE", "aucune donnée en base — vérifier l'ingestion"),
        ("PÉRIMÉE", "jeton migré, délisté ou source lâchée — sortir de l'univers"),
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

    # Toutes les séries d'abord : le retard d'une série se mesure contre la plus fraîche
    # du lot, pas contre la date du jour — une base ingérée hier soir n'est pas périmée.
    series = {base: lire_base(db, ticker_yahoo(base)) for base in bases}
    dernier = max((s[-1][0] for s in series.values() if s), default=None)
    if dernier:
        print(f"Barre la plus fraîche du lot : {dernier}\n")

    fiches = []
    for base in bases:
        ref = [] if a.sans_reseau else reference_binance(base)
        fiche = diagnostiquer(base, series[base], ref, dernier)
        fiches.append(fiche)
        _imprimer(fiche, ticker_yahoo(base))
    _conclure(fiches)


if __name__ == "__main__":
    main()
