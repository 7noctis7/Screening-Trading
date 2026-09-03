#!/usr/bin/env python3
"""Pourquoi le cœur QQQ de PRODUCTION ne vaut pas le QQQ que l'on peut acheter.

CE QUE CE DIAGNOSTIC TRANCHE. Le banc `make coeur-multi` a produit une ligne de contrôle
inattendue : le QQQ ETF replacé sur l'axe du preset rend -0,4 %/an de moins que le cœur
QQQ de production, avec t(alpha) = -6,15 sur 2 580 séances. Un écart minuscule, mais qui
n'est PAS du bruit — et sur une ligne censée mesurer exactement la même chose.

DEUX CAUSES POSSIBLES, ET ELLES N'ONT PAS LES MÊMES CONSÉQUENCES :

  A. SOURCE DIFFÉRENTE. `choose_history` prend le PREMIER alias frais parmi
     ["QQQ", "^NDX", "^IXIC"]. Si la base n'a pas de QQQ frais, la production mesure
     ^NDX — un INDICE, que personne ne peut acheter. L'écart serait alors les frais de
     l'ETF (0,20 %/an) plus l'écart de suivi : le tableau de bord surestimerait la
     moitié « cœur » du portefeuille d'environ 0,4 %/an, de façon permanente.

  B. DÉSALIGNEMENT POSITIONNEL. `blend_equity` recolle le cœur au preset par
     `core_ret[-k:] = xr[-k:]` — par POSITION. Or l'axe du preset est produit par
     `aligner_sans_trous`, qui ne garde que les dates où TOUS les titres cotent : c'est
     un SOUS-ENSEMBLE des séances américaines. Si les deux calendriers diffèrent, la
     production mélange des rendements qui ne tombent pas le même jour.

COMMENT ON LES DISTINGUE. Le cas A donne des séries quasi identiques au jour le jour
(corrélation ~0,999) avec un écart de rendement CONSTANT. Le cas B donne l'inverse : un
écart moyen nul mais une corrélation effondrée. Le diagnostic mesure les deux et laisse
les chiffres décider.

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

    print("\n  LECTURE :")
    if rho > 0.99 and abs(drift) > 0.001:
        print("    → CAS A. Les deux séries bougent ensemble au jour le jour,")
        print("      mais l'une rend systématiquement moins. C'est un écart de")
        print("      SOURCE, pas d'alignement : la production mesure un actif")
        print("      différent")
        print(f"      de celui qu'on achèterait, pour {abs(drift)*100:.2f} %/an sur la")
        print("      moitié « cœur ». À corriger dans QUANT_CORE_SPEC.")
    elif rho < 0.9:
        print("    → CAS B. La corrélation est effondrée alors que les deux séries")
        print("      décrivent le MÊME actif : les rendements ne tombent pas le même")
        print("      jour. C'est un désalignement positionnel dans `blend_equity`,")
        print("      quatrième occurrence du même défaut dans ce dépôt.")
    else:
        print("    → NI L'UN NI L'AUTRE nettement. Ne rien conclure : publier")
        print("      l'écart tel quel et rouvrir la question avec ces chiffres.")


if __name__ == "__main__":
    main()
