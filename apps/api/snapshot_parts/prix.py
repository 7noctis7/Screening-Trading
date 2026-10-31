"""Prix : chemins de base, alias Yahoo, chargement des séries, indices, courbes.

Extrait TEL QUEL de `apps/api/snapshot.py` le 31/10 (règle des 400 lignes par fichier) : le
texte des définitions n'a pas changé. `apps/api/snapshot.py` reste la façade et ré-exporte
chaque nom, donc `from apps.api.snapshot import X` fonctionne comme avant.
"""

from __future__ import annotations

from pathlib import Path

from apps.api.sections_data import SECTOR_DV as _SECTOR_DV
from apps.api.snapshot_parts.base import ROOT
from packages.data import data_providers


def _price_db_path() -> Path | None:
    """Chemin d'une base de prix réelle. Priorité : env QUANT_PRICE_DB, puis emplacements
    usuels (data/, Bureau/Desktop) → branche automatiquement votre ~/Desktop/YAHOO.db."""
    import os
    env = os.environ.get("QUANT_PRICE_DB")
    if env and Path(env).exists():
        return Path(env)
    home = Path.home()
    for p in (ROOT / "data" / "YAHOO.db", ROOT / "data" / "market.db",
              home / "Desktop" / "YAHOO.db", home / "Bureau" / "YAHOO.db",
              home / "Desktop" / "market.db"):
        if p.exists():
            return p
    return None


def _yahoo_aliases(sym: str, ac: str) -> list[str]:
    """Variantes de symbole au format Yahoo (pour retrouver crypto/forex/indices/commodités
    dans YAHOO.db). Objectif : maximiser la part de données RÉELLES.
    BTC/USDC → BTC-USD · EUR/USD → EURUSD=X · S&P 500 → ^GSPC · Gold → GC=F · BRK.B ↔ BRK-B."""
    _IDX = {"S&P 500": "^GSPC", "SP500": "^GSPC", "Nasdaq": "^IXIC", "Nasdaq 100": "^NDX",
            "Dow Jones": "^DJI", "Dow": "^DJI", "Russell 2000": "^RUT", "VIX": "^VIX",
            "FTSE 100": "^FTSE", "DAX": "^GDAXI", "CAC 40": "^FCHI", "Nikkei 225": "^N225"}
    _COMM = {"Gold": "GC=F", "Silver": "SI=F", "Crude Oil": "CL=F", "WTI": "CL=F",
             "Brent": "BZ=F", "Natural Gas": "NG=F", "Copper": "HG=F", "Corn": "ZC=F",
             "Wheat": "ZW=F"}
    out = [sym]
    if ac == "crypto":
        base = sym.split("/")[0] if "/" in sym else sym.replace("-USD", "").replace("USD", "")
        out += [f"{base}-USD", f"{base}USD", f"{base}-USDC", f"{base}-USDT", f"{base}USDT", base]
    elif ac == "forex" and "/" in sym:
        a, b = sym.split("/")[:2]
        out += [f"{a}{b}=X", f"{b}=X" if a == "USD" else f"{a}=X", f"{a}{b}"]
    elif ac == "commodity":
        out += [_COMM.get(sym, ""), f"{sym}=F"]
    elif ac == "index":
        out += [_IDX.get(sym, ""), f"^{sym}", sym.replace(" ", "")]
    elif ac in ("equity", "etf"):
        # convention Yahoo : classes d'actions notées avec '-' (BRK.B → BRK-B) et inversement
        if "." in sym:
            out.append(sym.replace(".", "-"))
        if "-" in sym:
            out.append(sym.replace("-", "."))
        out.append(sym.upper())
    return [s for s in dict.fromkeys(out) if s]   # dédupliqué, ordre préservé, sans vide


def _noms_sources(provs: list, prov_db, prov_crypto) -> list[str]:
    """Nom lisible de chaque provider, dans l'ordre où la fusion les consulte.

    Le lignage ne vaut que si la source porte un nom qu'un humain reconnaît : « base
    longue », « maj quotidienne », « crypto ». Un index de liste ne répond pas à la
    question « d'où vient cette barre ? »."""
    noms = []
    for p in provs:
        if p is prov_db:
            noms.append("base longue")
        elif p is prov_crypto:
            noms.append("crypto")
        else:
            noms.append("maj quotidienne")
    return noms


def _load_prices(instruments, sector_of, start, end, seed):
    """Charge l'OHLCV : base RÉELLE (YAHOO.db…) en priorité, sinon synthétique sectorisé
    (et synthétique en complément pour les symboles absents de la base). Renvoie
    (data, mode, real_syms) — `real_syms` = symboles à données RÉELLES (les autres sont synthétiques
    et NE doivent PAS apparaître en production/allocation/graphes : prix factices)."""
    data, real_syms = {}, set()
    _rebases: dict[str, float] = {}        # symbole → facteur de rebasage (QML-016)
    # symbole → jour → source qui l'a fourni
    _lignage: dict[str, dict[str, str]] = {}
    db = _price_db_path()
    prov_db = None
    if db is not None:
        try:
            from packages.data.providers.db_provider import DBPriceProvider
            prov_db = DBPriceProvider(db)
        except Exception:  # noqa: BLE001 — base illisible → tout en synthétique
            prov_db = None
    from packages.data.providers.db_provider import DBPriceProvider as _DBP
    # base CRYPTO dédiée (data/crypto.db via `make ingest-crypto`) — la crypto n'est pas dans YAHOO.db
    prov_crypto = None
    _crypto_db = ROOT / "data" / "crypto.db"
    if _crypto_db.exists():
        try:
            prov_crypto = _DBP(_crypto_db)
        except Exception:  # noqa: BLE001
            prov_crypto = None
    # couche de MISE À JOUR fraîche (data/market.db via `make daily`, yfinance) lue PAR-DESSUS
    # YAHOO.db → les barres récentes (jusqu'à aujourd'hui) sont RÉELLES sans toucher YAHOO.db.
    prov_updates = None
    _upd_db = ROOT / "data" / "market.db"
    if _upd_db.exists() and (db is None or _upd_db.resolve() != Path(db).resolve()):
        try:
            prov_updates = _DBP(_upd_db)
        except Exception:  # noqa: BLE001
            prov_updates = None
    # PRELOAD vectorisé (1 scan au lieu de N requêtes/symbole) : on précharge tout l'OHLCV des
    # alias de l'univers dans chaque provider LONG. Best-effort — repli SQL par symbole si échec.
    try:
        _eq_aliases, _cx_aliases = [], []
        for _m in instruments:
            _ac = _m.get("asset_class", "equity")
            (_cx_aliases if _ac == "crypto" else _eq_aliases).extend(_yahoo_aliases(_m["symbol"], _ac))
        for _p in (prov_db, prov_updates):
            if _p:
                _p.preload(_eq_aliases, "1d", start, end)
        if prov_crypto:
            prov_crypto.preload(_cx_aliases, "1d", start, end)
    except Exception:  # noqa: BLE001 — l'accélérateur ne doit jamais casser le chargement
        pass
    for m in instruments:
        s = m["symbol"]
        ac_m = m.get("asset_class", "equity")
        if ac_m == "crypto":
            provs = [prov_crypto] if prov_crypto else []
        else:
            provs = [p for p in (prov_db, prov_updates) if p]   # historique + maj fraîche (fusion)
        merged: dict = {}
        # EXTENSION SANS ÉCRASEMENT : la base longue garde la priorité, la couche de maj
        # complète les dates manquantes → pas de discontinuité raw/ajusté au milieu de
        # l'historique. Même règle que `merge_bars` depuis le 04/09 : les deux chemins
        # appliquaient des priorités OPPOSÉES sur les mêmes bases (0,71 %/an d'écart sur
        # le cœur QQQ). Le lignage enregistre quelle source a fourni chaque jour.
        _noms = _noms_sources(provs, prov_db, prov_crypto)
        _gots = []
        for prov in provs:
            got = []
            for alias in _yahoo_aliases(s, ac_m):
                got = prov.fetch_ohlcv(alias, "1d", start, end)
                if len(got) >= 50:
                    break
            _gots.append(got)
        # QML-016 : base longue remise dans le référentiel d'ajustement de la maj quand un
        # split/dividende postérieur à son export les sépare d'un facteur constant.
        if len(_gots) == 2 and _noms[:2] == ["base longue", "maj quotidienne"]:
            from packages.data.fusion_sources import rebaser_base_longue
            _gots[0], _f = rebaser_base_longue(_gots[0], _gots[1])
            if _f is not None:
                _rebases[s] = round(_f, 6)
        for _nom, got in zip(_noms, _gots, strict=False):
            for _b in got:
                _cle = _b.ts.isoformat()[:10]
                if _cle not in merged:
                    merged[_cle] = _b
                    _lignage.setdefault(s, {})[_cle] = _nom
        if len(merged) >= 250:
            data[s] = sorted(merged.values(), key=lambda x: x.ts)
            real_syms.add(s)
        else:
            drift, vol = _SECTOR_DV.get(sector_of[s], (0.07, 0.18))
            data[s] = data_providers.create(
                "synthetic", seed=seed, drift=drift, annual_vol=vol).fetch_ohlcv(s, "1d", start, end)
    real_syms -= _series_perimees(data, real_syms)
    if _rebases:                           # dit, jamais silencieux
        import logging
        logging.getLogger("snapshot.prix").warning(
            "base longue rebasée (ajustement postérieur à l'export) : %s",
            ", ".join(f"{k}×{v:g}" for k, v in sorted(_rebases.items())[:20]))
    n_real = len(real_syms)
    _src = db.name if db else ("market.db" if prov_updates else "crypto.db" if prov_crypto else "?")
    _src += " + maj market.db" if (db and prov_updates) else ""
    if n_real == 0:
        mode = "synthetic"
    elif n_real == len(instruments):
        mode = f"réel ({_src})"
    else:
        mode = f"mixte ({n_real} réels / {len(instruments)} via {_src})"
    return data, mode, real_syms


# Retard maximal toléré, en jours, sur la barre la plus fraîche de tout l'univers. On
# compare au PANNEAU, pas à la date du jour : un lundi férié ou une ingestion de la
# veille ne doivent condamner personne.
RETARD_MAX_JOURS = 60


def _series_perimees(data: dict, real_syms: set) -> set:
    """Symboles dont la dernière barre est trop vieille pour être tenue pour RÉELLE.

    LE DÉFAUT QUE ÇA CORRIGE. Une série s'arrête — jeton migré (MATIC→POL), délisté, ou
    source qui lâche — et rien ne le remarquait : le chargement ne regardait que le
    NOMBRE de barres. `HYPE/USDC`, arrêtée en août 2024, comptait pour un actif réel en
    septembre 2026 avec un cours vieux de deux ans. Le screener pouvait le classer, le
    dimensionnement le dimensionner, les graphiques l'afficher — tout cela sur un prix
    qui n'existe plus. Un prix périmé est pire qu'un prix absent : il a l'air d'un prix.

    Aucune donnée n'est modifiée ni supprimée : le symbole sort seulement de l'ensemble
    des séries RÉELLES, exactement comme s'il n'avait jamais eu assez d'historique.
    """
    derniers = {s: max((b.ts for b in data.get(s, [])), default=None)
                for s in real_syms}
    fraiches = [d for d in derniers.values() if d is not None]
    if not fraiches:
        return set()
    reference = max(fraiches)
    trop_vieux = RETARD_MAX_JOURS
    return {s for s, d in derniers.items()
            if d is None or (reference - d).days > trop_vieux}


def _index_series(aliases: list[str], start, end,
                  fallback: list[float]) -> tuple[list[float], list[str], bool]:
    """Historique daté : fusion même alias, fraîcheur obligatoire, puis réseau si périmé."""
    from packages.data.index_history import (
        choose_history,
        interrogeables_en_ligne,
        merge_bars,
    )
    from packages.data.providers.db_provider import DBPriceProvider
    histories: dict[str, dict] = {alias: {} for alias in aliases}
    # L'ORDRE EST LA POLITIQUE : la base longue d'abord, elle garde la priorité ; les
    # suivantes ne comblent que les dates absentes (cf. `fusion_sources`).
    _dbs = [(_price_db_path(), "base longue"),
            (ROOT / "data" / "market.db", "maj quotidienne"),
            (ROOT / "data" / "crypto.db", "crypto")]
    lignage: dict[str, dict[str, str]] = {alias: {} for alias in aliases}
    for _dbp, _nom in _dbs:
        if _dbp is None or not Path(_dbp).exists():
            continue
        try:
            prov = DBPriceProvider(_dbp)
            for a in aliases:
                bars = prov.fetch_ohlcv(a, "1d", start, end)
                merge_bars(histories[a], bars, source=_nom, lignage=lignage[a])
        except Exception:  # noqa: BLE001
            continue
    selected = choose_history(aliases, histories, end)
    if selected and selected.fresh:
        return list(selected.closes), list(selected.dates), True
    try:
        from packages.common.net import online
        if online():
            from packages.data.providers.yfinance_provider import YFinanceProvider
            provider = YFinanceProvider()
            # `VIX` et `SPX` sont nos noms de BASE, pas des tickers Yahoo : les
            # demander au réseau ne peut rien rendre (« $VIX: possibly delisted »
            # à chaque build). Les proxys cotés (`SPY`, `QQQ`) restent interrogés —
            # vrais tickers, et seul repli quand l'indice lui-même ne répond pas.
            for a in interrogeables_en_ligne(aliases):
                merge_bars(histories[a], provider.fetch_ohlcv(a, "1d", start, end))
    except Exception:  # noqa: BLE001
        pass
    selected = choose_history(aliases, histories, end)
    if selected and selected.fresh:
        return list(selected.closes), list(selected.dates), True
    return fallback, [], False


def _index_closes(aliases: list[str], start, end,
                   fallback: list[float]) -> tuple[list[float], bool]:
    """Cours seuls. Jeter les dates a un COÛT : cf. `_index_closes_dates`."""
    closes, _dates, real = _index_series(aliases, start, end, fallback)
    return closes, real


def _index_closes_dates(aliases: list[str], start, end,
                        fallback: list[float]) -> tuple[list[float], list[str], bool]:
    """Cours ET dates. `_index_closes` jetait `_dates` juste avant qu'on en ait besoin.

    Conséquence mesurée (04/09) : la courbe QQQ arrivait sans son calendrier,
    et `compute_attribution` la comparait au preset PAR POSITION — deux calendriers
    différents (indices vs univers négociable). Résultat publié : bêta 0,006 et
    corrélation 0,008 pour un portefeuille long-only d'actions américaines. Le chiffre
    était absurde et rien ne le signalait."""
    return _index_series(aliases, start, end, fallback)


def _curve_stats(eq: list[float], *, compte_reel: bool = False,
                 dates: list[str] | None = None) -> dict:
    """KPIs d'une courbe d'equity. Ratios via perf_summary (SOURCE UNIQUE DE VÉRITÉ) ;
    profit_factor/win_rate dérivés des rendements quotidiens (gains/pertes).

    `compte_reel=True` → la courbe est la valeur d'un COMPTE, pas une simulation : elle peut
    contenir des versements et des retraits. On les neutralise (rendement pondéré dans le temps,
    cf. packages/portfolio/twr) avant tout calcul. Sans cela, un virement se retrouve compté
    comme un gain ou une perte, et contamine rendement, Sharpe ET drawdown maximum.
    """
    import numpy as _np

    from packages.portfolio.metrics import perf_summary
    e = _np.asarray(eq, dtype=float)
    if e.size < 30:
        return {"available": False}
    r = e[1:] / e[:-1] - 1
    _flux: dict | None = None
    if compte_reel:
        from packages.portfolio.twr import flow_report, twr
        _t = twr([float(x) for x in e])
        if _t.get("available"):
            r = _np.asarray(_t["returns"], dtype=float)   # sous-périodes, versements exclus
            _flux = flow_report([float(x) for x in e], dates=dates)
    ps = perf_summary(r)                                  # cagr/sharpe/sortino/maxdd unifiés
    if not ps.get("available"):
        return {"available": False}
    gains, losses = float(r[r > 0].sum()), float(-r[r < 0].sum())
    out = {"available": True, "n": ps["n"],           # fenêtre réelle → affichable, comparable
           "cagr": ps["cagr"], "total_return": ps["total_return"],
           "sharpe": ps["sharpe"], "sortino": ps["sortino"],
           "max_drawdown": ps["max_drawdown"], "win_rate": round(float((r > 0).mean()), 3),
           "profit_factor": round(gains / losses, 2) if losses > 0 else 0.0}
    if _flux is not None:
        out["flux"] = _flux                               # mouvements neutralisés, montants, dates
    return out


def _r(x, nd=3):
    """Arrondi NaN-safe (→ None) pour les payloads JSON."""
    return round(float(x), nd) if isinstance(x, (int, float)) and x == x else None
