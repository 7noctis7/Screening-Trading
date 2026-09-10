"""MFE / MAE : combler ce que le chemin de réparation n'a jamais capturé.

LE TROU. `scripts/reconcilier_journal.py:262` passe `None` comme série de prix à
`_close_record` : toute fermeture reconstruite naît sans MFE ni MAE. Sur le journal
réel du 10/09, **36 des 40 positions closes** viennent de ce chemin — d'où « capture
médiane du potentiel : mesurable sur 4 positions ». Sans MFE, aucune recherche de
sortie n'est possible : on ne peut pas dire si un trade a rendu ses gains sans savoir
combien il en avait.

POURQUOI COMBLER EST LÉGITIME ICI. Une MFE est un FAIT sur le chemin de prix entre
deux dates, lu dans la base locale. Ce n'est pas une reconstruction de décision,
contrairement à un prix de sortie retrouvé après coup : on mesure ce que le marché a
fait, pas ce que le système aurait décidé.

CE QU'ON REFUSE. Des CLÔTURES SEULES ne suffisent pas. Sans haut ni bas, l'excursion
est sous-estimée — et une MFE minorée fait passer une sortie médiocre pour une bonne,
soit exactement l'inverse de ce que P0-2 cherche à mesurer. Dans ce cas : `None`.
"""

from __future__ import annotations

import dataclasses


def _barres_actions(symbole: str, annees: int) -> list:
    """Barres de la base ACTIONS (avec repli en ligne). `[]` si rien."""
    from packages.data.price_loader import load_bars
    return load_bars(symbole, years=annees) or []


def _lignes_crypto(symbole: str, annees: int) -> list[dict]:
    """Lignes brutes de `crypto.db`, HAUTS ET BAS COMPRIS.

    `user_analysis._bars_crypto` lit déjà cette base mais ne garde que les clôtures :
    aucune MFE crypto n'était donc calculable. Or `read_prices_rows` expose bien
    `high`/`low` — la donnée était là, personne ne la lisait.
    """
    from datetime import UTC, datetime, timedelta

    from packages.data.engine import read_prices_rows
    limite = (datetime.now(UTC) - timedelta(days=365 * annees)).date().isoformat()
    rows = read_prices_rows("crypto.db", symbols=[symbole]) or []
    return [r for r in sorted(rows, key=lambda r: r.get("ts") or "")
            if str(r.get("ts") or "")[:10] >= limite]


def barres_locales(symbole: str, annees: int = 3) -> list:
    """Barres du symbole : base ACTIONS d'abord, base CRYPTO ensuite.

    `load_bars` ne consulte que la base actions — `_price_db_path()` ne liste pas
    `crypto.db`. Sans ce repli, toute position crypto sortait « sans barres ».
    """
    from types import SimpleNamespace
    try:
        bars = _barres_actions(symbole, annees)
    except Exception:  # noqa: BLE001
        bars = []
    if bars:
        return bars
    try:
        lignes = _lignes_crypto(symbole, annees)
    except Exception:  # noqa: BLE001
        return []
    return [SimpleNamespace(ts=str(r.get("ts") or "")[:10],
                            high=r.get("high"), low=r.get("low"),
                            close=r.get("close")) for r in lignes]


def symbole_barres(symbole: str) -> str:
    """Symbole tel que les fournisseurs de PRIX l'indexent.

    Le journal stocke la paire telle que le courtier la nomme (`BTC/USDC`). Aucun
    fournisseur d'actions ne connaît cette forme : la requête part quand même, échoue,
    et dumpe une page d'erreur HTML dans le terminal. Mesuré le 10/09 — 77 lignes
    « sans barres exploitables », presque toutes du crypto jamais traduit.
    """
    s = (symbole or "").upper()
    return s.split("/")[0] + "-USD" if "/" in s else s


def _jour(ts) -> str | None:
    """Date ISO d'une barre. La base actions rend un `datetime`, la base crypto une
    chaîne — une seule des deux formes suffirait à faire planter le comblement."""
    if ts is None:
        return None
    return (ts.isoformat() if hasattr(ts, "isoformat") else str(ts))[:10] or None


def serie_pour_mfe(bars) -> list[dict] | None:
    """Barres → série `{t, h, l}` pour `mfe_mae`. `None` si les hauts/bas manquent.

    Le repli yfinance de `price_loader` ne rend que `ts/close/volume` : accepter ces
    barres reviendrait à publier une excursion calculée sur des clôtures sous le nom
    de MFE.
    """
    if not bars:
        return None
    out = []
    for b in bars:
        haut, bas = getattr(b, "high", None), getattr(b, "low", None)
        jour = _jour(getattr(b, "ts", None))
        if haut is None or bas is None or jour is None:
            return None
        out.append({"t": jour, "h": float(haut), "l": float(bas)})
    return out or None


def combler(trades: list, fournisseur) -> dict:
    """Calcule MFE/MAE sur les trades CLOS qui n'en ont pas.

    Args:
        trades: les enregistrements du journal.
        fournisseur: `symbole -> barres`. Peut lever : l'échec d'un symbole ne doit pas
            interrompre les autres.

    Returns:
        `{trades, combles, ignores, sans_donnee}` — `trades` est la liste RÉÉCRITE (les
        autres restent inchangés). Rien n'est écrit en base ici : cette fonction est
        pure, c'est le script appelant qui décide d'appliquer.
    """
    from packages.execution.live_roundtrip import mfe_mae

    sortie, combles, ignores, sans_donnee = [], 0, 0, 0
    cache: dict[str, list | None] = {}
    for t in trades:
        # On ne réécrit JAMAIS une mesure existante : elle vient peut-être d'une source
        # plus fine que la base quotidienne (bougies intraday du courtier).
        if t.exit_ts is None or t.mfe is not None:
            ignores += 1
            sortie.append(t)
            continue
        cle = symbole_barres(t.instrument)
        if cle not in cache:
            try:
                cache[cle] = serie_pour_mfe(fournisseur(cle))
            except Exception:  # noqa: BLE001 — un symbole muet n'arrête pas les autres
                cache[cle] = None
        fe, ae = mfe_mae(cache[cle], t.entry_ts, t.exit_ts, t.entry_price)
        if fe is None:
            sans_donnee += 1
            sortie.append(t)
            continue
        combles += 1
        sortie.append(dataclasses.replace(t, mfe=fe, mae=ae))
    return {"trades": sortie, "combles": combles, "ignores": ignores,
            "sans_donnee": sans_donnee}


def rapport(r: dict) -> str:
    """Une ligne par issue. Le silence sur les non-comblés cacherait la couverture."""
    total = r["combles"] + r["ignores"] + r["sans_donnee"]
    return (f"{total} enregistrement(s) examiné(s) — "
            f"{r['combles']} comblé(s), {r['ignores']} déjà mesuré(s) ou ouvert(s), "
            f"{r['sans_donnee']} sans barres exploitables (haut/bas requis).")
