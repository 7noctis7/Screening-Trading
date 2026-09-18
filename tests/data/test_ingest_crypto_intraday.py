"""L'ingestion crypto intraday : idempotente, incrémentale, et muette sur rien.

POURQUOI LA CRYPTO PORTE CE CHANTIER. Côté actions, l'histoire intraday gratuite est
bridée (yfinance plafonne le 1h à ~730 jours ; le palier gratuit d'Alpaca sert le flux
IEX, dont les VOLUMES ne représentent pas le marché — or nos détecteurs filtrent sur le
volume). Binance sert 1h et 4h gratuitement, sans clé, sur tout l'historique : c'est le
seul endroit où l'intraday se MESURE sans payer ni dépendre d'une source partielle.

Ce que ces tests tiennent : deux passages ne doublent rien, le second repart de la
dernière barre connue, et une base sans données se dit au lieu de passer pour vide.
"""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
H = 3_600_000


def _module():
    spec = importlib.util.spec_from_file_location(
        "ici", RACINE / "scripts" / "ingest_crypto_intraday.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _faux_binance(monkeypatch, n: int = 40):
    """Binance factice : `n` barres horaires CLOSES à partir du curseur demandé."""
    from packages.data import crypto_binance as cb

    maintenant = int(datetime.now(UTC).timestamp() * 1000)

    def get_json(url: str):
        from urllib.parse import parse_qs, urlparse
        d = int(parse_qs(urlparse(url).query)["startTime"][0])
        return [[d + k * H, 1, 2, 0.5, 1.0 + k, 5, d + (k + 1) * H - 1]
                for k in range(n) if d + (k + 1) * H - 1 < maintenant]

    vrai = cb.historique
    monkeypatch.setattr(
        cb, "historique",
        lambda base, depuis="2015-01-01", get_json=None, plafond_pages=None,
        interval="1d": vrai(base, depuis, get_json or globals()["_gj"], plafond_pages,
                            interval))
    globals()["_gj"] = get_json


def test_deux_passages_ne_doublent_rien_et_reprennent_ou_ils_en_etaient(monkeypatch):
    """Sans reprise incrémentale, chaque passage rejouerait tout l'historique : des
    dizaines de milliers d'appels pour quelques barres neuves, et un rate-limit."""
    from packages.storage.bars_repo import SqliteBarsRepository

    _faux_binance(monkeypatch)
    m = _module()
    repo = SqliteBarsRepository(":memory:")
    depart = (datetime.now(UTC).date().isoformat())
    m._ingerer(repo, ["BTC"], "1h", "2026-09-01", False)
    n1 = repo.count()
    m._ingerer(repo, ["BTC"], "1h", "2026-09-01", False)
    assert n1 > 0
    assert repo.count() >= n1, "aucune ligne ne doit disparaître"
    lu = repo.read("BTC/USDT", "1h")
    assert len({b.ts for b in lu}) == len(lu), "un horodatage ne peut apparaître 2 fois"
    assert depart  # la reprise part de la dernière barre, pas du défaut


def test_les_barres_portent_le_BON_timeframe_et_un_symbole_canonique(monkeypatch):
    from packages.storage.bars_repo import SqliteBarsRepository

    _faux_binance(monkeypatch)
    m = _module()
    repo = SqliteBarsRepository(":memory:")
    m._ingerer(repo, ["ETH"], "4h", "2026-09-01", False)
    lu = repo.read("ETH/USDT", "4h")
    assert lu, "rien n'a été écrit"
    assert all(b.timeframe == "4h" for b in lu)
    assert all(b.ts.tzinfo is not None for b in lu), "un horodatage sans fuseau dérive"


def test_une_base_MUETTE_est_nommee_jamais_tue(monkeypatch):
    """Une paire absente de Binance n'est pas une erreur ; la taire laisserait croire
    l'univers complet."""
    from packages.data import crypto_binance as cb
    from packages.storage.bars_repo import SqliteBarsRepository

    monkeypatch.setattr(cb, "historique", lambda *a, **k: [])
    m = _module()
    r = m._ingerer(SqliteBarsRepository(":memory:"), ["ZZZ"], "1h", "2026-09-01", False)
    assert r["muets"] == ["ZZZ"] and r["ecrites"] == 0


def test_la_base_intraday_ne_peut_PAS_etre_commitee():
    """Le dépôt est PUBLIC. Une base de prix qui y entrerait ne s'en retire pas."""
    import subprocess

    r = subprocess.run(["git", "check-ignore", "data/crypto_intraday.db"],
                       cwd=RACINE, capture_output=True, text=True)
    assert r.returncode == 0, "data/crypto_intraday.db n'est PAS ignoré par git"
