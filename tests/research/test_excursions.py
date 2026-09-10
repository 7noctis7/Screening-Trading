"""Combler MFE/MAE — la mesure sans laquelle aucune recherche de sortie n'est possible.

`reconcilier_journal.py:262` passe `None` comme série de prix à `_close_record` : toute
fermeture reconstruite naît donc sans MFE ni MAE. Sur le journal réel du 10/09, 36 des
40 positions closes viennent de ce chemin — d'où « capture mesurable sur 4 positions ».

Une MFE est un FAIT sur le chemin de prix entre deux dates, lu dans la base locale. La
calculer après coup est légitime, contrairement à un prix de sortie reconstruit. Mais
elle exige des HAUTS et des BAS : sur des clôtures seules, l'excursion est sous-estimée,
et une MFE minorée ferait passer une sortie médiocre pour une bonne.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from packages.core.models import AssetClass, Side, TradeRecord
from packages.research.excursions import combler, serie_pour_mfe

_T0 = datetime(2026, 8, 1, tzinfo=UTC)


def _bar(jour: int, haut: float, bas: float):
    return SimpleNamespace(ts=_T0 + timedelta(days=jour), open=100.0, high=haut,
                           low=bas, close=(haut + bas) / 2, volume=1000.0)


def _trade(tid: str = "t1", *, mfe=None, mae=None, ferme: bool = True) -> TradeRecord:
    return TradeRecord(
        id=tid, instrument="QQQ", asset_class=AssetClass.EQUITY, venue="Alpaca",
        side=Side.LONG, qty=1.0, entry_ts=_T0, entry_price=100.0, avg_price=100.0,
        exit_ts=_T0 + timedelta(days=3) if ferme else None,
        exit_price=104.0 if ferme else None, mfe=mfe, mae=mae)


# ── la série : haut/bas obligatoires ────────────────────────────────────────

def test_des_barres_completes_donnent_une_serie():
    s = serie_pour_mfe([_bar(0, 110.0, 95.0), _bar(1, 112.0, 99.0)])
    assert s is not None and len(s) == 2
    assert s[0]["h"] == 110.0 and s[0]["l"] == 95.0


def test_des_CLOTURES_SEULES_ne_donnent_PAS_de_serie():
    """Le repli yfinance ne rend ni haut ni bas. Une MFE calculée sur des clôtures
    sous-estime l'excursion — et une MFE minorée fait passer une sortie médiocre pour
    une bonne. Mieux vaut `None` qu'un chiffre flatteur."""
    closes = [SimpleNamespace(ts=_T0, close=110.0, volume=0.0)]
    assert serie_pour_mfe(closes) is None


def test_une_serie_vide_rend_None():
    assert serie_pour_mfe([]) is None
    assert serie_pour_mfe(None) is None


# ── le comblement ───────────────────────────────────────────────────────────

def _fournisseur(bars):
    return lambda _symbole: bars


def test_la_MFE_et_la_MAE_sont_calculees_sur_la_FENETRE_du_trade():
    bars = [_bar(0, 105.0, 98.0), _bar(1, 118.0, 101.0), _bar(2, 110.0, 92.0),
            _bar(9, 200.0, 50.0)]                      # HORS fenêtre : ignorée
    r = combler([_trade()], _fournisseur(bars))
    assert r["combles"] == 1
    t = r["trades"][0]
    assert t.mfe == 0.18       # 118 / 100 − 1, pas 200
    assert t.mae == -0.08      # 92 / 100 − 1, pas 50


def test_un_trade_qui_a_DEJA_sa_MFE_n_est_pas_recalcule():
    """On ne réécrit jamais une mesure existante : elle vient peut-être d'une source
    plus fine que la base quotidienne."""
    r = combler([_trade(mfe=0.42, mae=-0.01)], _fournisseur([_bar(1, 118.0, 92.0)]))
    assert r["combles"] == 0
    assert r["trades"][0].mfe == 0.42


def test_un_trade_OUVERT_est_ignore():
    """Sans sortie, la fenêtre n'est pas fermée : l'excursion n'est pas finale."""
    r = combler([_trade(ferme=False)], _fournisseur([_bar(1, 118.0, 92.0)]))
    assert r["combles"] == 0 and r["ignores"] == 1


def test_sans_barre_dans_la_fenetre_on_ne_comble_RIEN():
    r = combler([_trade()], _fournisseur([_bar(40, 118.0, 92.0)]))
    assert r["combles"] == 0 and r["sans_donnee"] == 1
    assert r["trades"][0].mfe is None


def test_sans_haut_ni_bas_on_ne_comble_RIEN():
    closes = [SimpleNamespace(ts=_T0 + timedelta(days=1), close=118.0, volume=0.0)]
    r = combler([_trade()], _fournisseur(closes))
    assert r["combles"] == 0 and r["sans_donnee"] == 1


def test_un_fournisseur_qui_ECHOUE_ne_casse_rien():
    """Une base absente ne doit pas interrompre le comblement des autres lignes."""
    def casse(_):
        raise RuntimeError("base indisponible")
    r = combler([_trade()], casse)
    assert r["combles"] == 0 and r["sans_donnee"] == 1


# ── le câblage : le chemin de réparation doit fournir une série ─────────────

def test_le_chemin_de_reparation_ne_passe_plus_None():
    """Un module qui passe ses tests mais n'est pas atteint par le chemin réel n'est
    pas terminé. Ce test lit la SOURCE : `reconcilier_journal` doit fournir une série
    à `_close_record`, sans quoi toute fermeture reconstruite renaîtra sans MFE."""
    from pathlib import Path
    src = (Path(__file__).resolve().parents[2] / "scripts"
           / "reconcilier_journal.py").read_text(encoding="utf-8")
    appels = [x for x in src.splitlines()
              if "_close_record(" in x and "def " not in x]
    assert appels, "aucun appel à `_close_record` trouvé — le test a perdu sa cible"
    assert all("None" not in a for a in appels), (
        "une fermeture reconstruite naîtrait sans MFE : "
        f"{[a.strip() for a in appels if 'None' in a]}")


# ── crypto : le symbole du journal n'est pas celui du fournisseur ───────────

def test_une_paire_crypto_est_traduite_pour_la_base():
    """`BTC/USDC` n'existe chez aucun fournisseur d'actions : la requête part, échoue,
    et dumpe une page d'erreur HTML dans le terminal. Mesuré le 10/09 : 77 lignes
    « sans barres » — presque toutes du crypto jamais traduit."""
    from packages.research.excursions import symbole_barres
    assert symbole_barres("BTC/USDC") == "BTC-USD"
    assert symbole_barres("AAVE/USDC") == "AAVE-USD"
    assert symbole_barres("AAPL") == "AAPL"
    assert symbole_barres("ASML.AS") == "ASML.AS"


def test_le_comblement_utilise_le_symbole_TRADUIT():
    """Le fournisseur doit recevoir le symbole du marché, pas celui du journal."""
    vus = []

    def fournisseur(sym):
        vus.append(sym)
        return [_bar(1, 118.0, 92.0), _bar(2, 110.0, 95.0)]

    t = TradeRecord(
        id="c1", instrument="BTC/USDC", asset_class=AssetClass.CRYPTO, venue="Alpaca",
        side=Side.LONG, qty=1.0, entry_ts=_T0, entry_price=100.0, avg_price=100.0,
        exit_ts=_T0 + timedelta(days=3), exit_price=104.0)
    combler([t], fournisseur)
    assert vus == ["BTC-USD"]
