#!/usr/bin/env python3
"""Pourquoi le cœur QQQ de PRODUCTION ne vaut pas le QQQ que l'on peut acheter.

CE QUE CE DIAGNOSTIC TRANCHE. Le banc `make coeur-multi` a produit une ligne de contrôle
inattendue : le QQQ ETF replacé sur l'axe du preset rend -0,4 %/an de moins que le cœur
QQQ de production, avec t(alpha) = -6,15 sur 2 580 séances. Un écart minuscule, mais qui
n'est PAS du bruit — et sur une ligne censée mesurer exactement la même chose.

DEUX HYPOTHÈSES ONT ÉTÉ ÉMISES PUIS FALSIFIÉES PAR CE DIAGNOSTIC (03/09). Elles restent
écrites : une hypothèse abandonnée en silence se re-teste six mois plus tard.

  A. « La production mesure ^NDX, un indice non achetable. » FAUX — le run affiche
     SOURCE RETENUE : QQQ (frais). C'est bien l'ETF.
  B. « Les calendriers diffèrent, `blend_equity` recolle par position. » FAUX — zéro
     séance d'écart dans les deux sens sur la fenêtre commune. L'alignement positionnel
     tombe juste ici, parce que les deux calendriers coïncident exactement.

CE QUI RESTE, ET QUE LA LECTURE DU CODE ÉTABLIT. Les deux chemins fusionnent YAHOO.db et
market.db dans des sens OPPOSÉS, sur le même symbole :

  `_load_prices`   `merged.setdefault(jour, barre)`  → le PREMIER gagne : YAHOO.db garde
                   la priorité, market.db ne comble que les dates manquantes. Le
                   commentaire dit pourquoi : « pas de discontinuité d'ajustement (raw
                   vs adjusted) au milieu de l'historique ».
  `_index_series`  `merge_bars` fait `target[jour] = close` → le DERNIER gagne :
                   market.db ÉCRASE YAHOO.db sur toutes les dates communes.

Si les deux bases n'ont pas le même niveau d'ajustement (dividendes, splits), la série
de production est RECOLLÉE entre deux référentiels, avec un saut artificiel à la date de
raccord. Étalé sur onze ans, ce saut se lit comme une dérive régulière — exactement le
-0,71 %/an observé. Le bloc « COMPARAISON DES DEUX BASES » ci-dessous le mesure plutôt
que de le supposer : si les clôtures diffèrent aux dates communes, l'affaire est close.

    export QUANT_PRICE_DB=/chemin/YAHOO.db
    python scripts/diag_coeur_qqq.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ALIAS = ["QQQ", "^NDX", "^IXIC"]


def _rendements_par_date(dates: list[str], closes: list[float]) -> dict[str, float]:
    """Rendements INDEXÉS PAR DATE. C'est la seule façon d'apparier sans supposer."""
    out = {}
    for k in range(1, min(len(dates), len(closes))):
        a, b = closes[k - 1], closes[k]
        if a and b and a > 0:
            out[dates[k]] = b / a - 1.0
    return out


def _annualise(ecarts: list[float]) -> float:
    return (sum(ecarts) / len(ecarts)) * 252.0 if ecarts else 0.0


def _correlation(a: list[float], b: list[float]) -> float:
    n = len(a)
    if n < 30 or len(b) != n:
        return 0.0
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((x - mb) ** 2 for x in b)
    if va <= 0 or vb <= 0:
        return 0.0
    return sum((a[i] - ma) * (b[i] - mb) for i in range(n)) / (va * vb) ** 0.5


def _source(start, end, fallback) -> tuple[list[str], list[float], str]:
    """Quel alias la production utilise VRAIMENT, et sur quelles dates."""
    from apps.api.snapshot import _index_series, _price_db_path
    from packages.data.index_history import choose_history, merge_bars
    from packages.data.providers.db_provider import DBPriceProvider
    histories: dict[str, dict] = {a: {} for a in ALIAS}
    for _dbp in (_price_db_path(), ROOT / "data" / "market.db"):
        if _dbp is None or not Path(_dbp).exists():
            continue
        try:
            prov = DBPriceProvider(_dbp)
            for a in ALIAS:
                merge_bars(histories[a], prov.fetch_ohlcv(a, "1d", start, end))
        except Exception:  # noqa: BLE001
            continue
    choisi = choose_history(ALIAS, histories, end)
    etat = ("frais" if choisi and choisi.fresh else "PÉRIMÉ")
    nom = f"{choisi.alias} ({etat})" if choisi else "aucun"
    for a in ALIAS:
        n = len(histories.get(a, {}))
        print(f"    {a:<8} {n:>6} barres en base"
              + ("" if n >= 250 else "   ← moins de 250 : ÉCARTÉ par choose_history"))
    closes, dates, _reel = _index_series(ALIAS, start, end, fallback)
    return dates, closes, nom


def main() -> None:
    print(__doc__.split("    export")[0].rstrip())
    print("\nConstruction du snapshot… ~30-60 s\n")
    from datetime import UTC, datetime, timedelta

    from apps.api.snapshot import _HISTORY_DAYS, build_snapshot

    snap = build_snapshot()
    cur = snap.get("index_core_curves", {})
    axe = list(cur.get("dates", []))
    etf = list((cur.get("diversifiants") or {}).get("QQQ") or [])
    if not axe or not etf:
        print("Axe ou série ETF absents — relancer après un `make sync`.")
        return

    fin = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    debut = fin - timedelta(days=_HISTORY_DAYS)
    print("  Alias interrogés pour le cœur de production :")
    d_prod, c_prod, nom = _source(debut, fin, list(cur.get("qqq", [])))
    print(f"\n  SOURCE RETENUE PAR LA PRODUCTION : {nom}")

    if not d_prod:
        print("  ⚠️ Aucune date renvoyée : la production tourne sur le REPLI.")
        return
    print(f"  série production : {len(c_prod)} clôtures, {d_prod[0]} → {d_prod[-1]}")
    print(f"  axe du preset    : {len(axe)} dates,     {axe[0]} → {axe[-1]}")

    manquantes = sorted(set(d_prod) - set(axe))
    ajoutees = sorted(set(axe) - set(d_prod))
    couvert = [d for d in d_prod if axe[0] <= d <= axe[-1]]
    hors = len([d for d in manquantes if axe[0] <= d <= axe[-1]])
    print(f"\n  Séances dans la source mais PAS dans l'axe du preset : {hors} "
          f"(sur {len(couvert)} dans la fenêtre commune)")
    print(f"  Séances dans l'axe mais pas dans la source            : {len(ajoutees)}")

    r_prod = _rendements_par_date(d_prod, c_prod)
    r_etf = _rendements_par_date(axe, [x if x is not None else 0.0 for x in etf])
    communes = sorted(set(r_prod) & set(r_etf))
    if len(communes) < 250:
        print("\n  Moins de 250 dates communes — rien de concluant à dire.")
        return
    a = [r_prod[d] for d in communes]
    b = [r_etf[d] for d in communes]
    ecarts = [b[i] - a[i] for i in range(len(a))]
    rho = _correlation(a, b)
    drift = _annualise(ecarts)
    print(f"\n  Sur {len(communes)} dates COMMUNES ({communes[0]} → {communes[-1]}) :")
    print(f"    corrélation quotidienne source/ETF : {rho:+.4f}")
    print(f"    écart annualisé (ETF − production) : {drift*100:+.2f} %/an")

    _comparer_bases(debut, fin)

    print("\n  LECTURE :")
    if rho > 0.99 and abs(drift) > 0.001:
        print("    → MÊME TICKER, SÉRIES DIFFÉRENTES. Les deux bougent ensemble")
        print("      au jour le jour (rho > 0,99) mais l'une rend moins. Ce")
        print("      n'est ni un problème d'instrument ni d'alignement : c'est que les")
        print("      deux chemins ne FUSIONNENT PAS les bases dans le même sens.")
        print(f"      Effet : {abs(drift)*100:.2f} %/an sur la moitié « cœur ».")
        print("      Voir la comparaison des bases ci-dessus pour savoir")
        print("      laquelle des deux séries est la bonne.")
    elif rho < 0.9:
        print("    → DÉSALIGNEMENT. La corrélation est effondrée alors que les deux")
        print("      séries décrivent le MÊME actif : les rendements ne tombent pas le")
        print("      même jour. Défaut d'alignement positionnel, à corriger en amont.")
    else:
        print("    → NI L'UN NI L'AUTRE nettement. Ne rien conclure : publier")
        print("      l'écart tel quel et rouvrir la question avec ces chiffres.")


def _closes_par_date(chemin, symbole: str, start, end) -> dict[str, float]:
    from packages.data.providers.db_provider import DBPriceProvider
    if chemin is None or not Path(chemin).exists():
        return {}
    try:
        prov = DBPriceProvider(chemin)
        return {b.ts.date().isoformat(): float(b.close)
                for b in prov.fetch_ohlcv(symbole, "1d", start, end)}
    except Exception:  # noqa: BLE001
        return {}


def _comparer_bases(start, end, symbole: str = "QQQ") -> None:
    """Les deux bases donnent-elles les MÊMES clôtures aux MÊMES dates ?

    C'est la question qui tranche. Si oui, le sens de fusion n'a aucune importance et
    l'écart vient d'ailleurs. Si non, la série de production est un recollage entre deux
    référentiels d'ajustement, et le saut au raccord EST la dérive mesurée.
    """
    from apps.api.snapshot import _price_db_path
    hist = _closes_par_date(_price_db_path(), symbole, start, end)
    maj = _closes_par_date(ROOT / "data" / "market.db", symbole, start, end)
    print(f"\n  COMPARAISON DES DEUX BASES sur {symbole} :")
    if not maj:
        print("    market.db absente ou sans ce symbole → une seule source, "
              "le sens de fusion n'a aucun effet. L'écart vient d'ailleurs.")
        return
    print(f"    base historique : {len(hist)} clôtures · market.db : {len(maj)}")
    communes = sorted(set(hist) & set(maj))
    if not communes:
        print("    aucune date commune → market.db ne fait qu'ÉTENDRE l'historique ; "
              "les deux chemins voient alors la même chose.")
        return
    ratios = [maj[d] / hist[d] for d in communes if hist[d] > 0]
    ecarts = [r for r in ratios if abs(r - 1.0) > 1e-6]
    print(f"    dates communes : {len(communes)} ({communes[0]} → {communes[-1]})")
    print(f"    clôtures qui DIFFÈRENT : {len(ecarts)} ({len(ecarts)/len(ratios):.0%})")
    if not ecarts:
        print("    → les deux bases sont d'accord partout. Le sens de fusion est SANS")
        print("      effet : la cause de l'écart est ailleurs, ne pas s'arrêter là.")
        return
    lo, hi = min(ratios), max(ratios)
    print(f"    ratio market.db / historique : min {lo:.4f} · max {hi:.4f}")
    print(f"    → NIVEAUX D'AJUSTEMENT DIFFÉRENTS sur {len(ecarts)} dates.")
    print("      `_index_series` laisse market.db écraser l'historique ;")
    print("      `_load_prices` fait l'inverse. La courbe de production est donc")
    print("      RECOLLÉE entre deux référentiels — c'est le défaut à corriger, et")
    print("      c'est `_load_prices` qui a raison (son commentaire l'explique).")


if __name__ == "__main__":
    main()
