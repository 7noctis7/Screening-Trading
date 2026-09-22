"""Le portefeuille lu MAINTENANT — et ce qu'il refuse de laisser croire.

Le bandeau du site affichait « LIVE · il y a 15min ». Ces quinze minutes ne sont pas un
retard de la donnée : c'est la période de reconstruction du snapshot. Or le snapshot
mélange deux rythmes — un screening sur barres QUOTIDIENNES, dont la fenêtre s'arrête à
minuit, et un portefeuille qui bouge à chaque seconde de séance. Raccourcir le TTL
aurait
payé un recalcul complet du premier pour rafraîchir le second.

Cette route lit le courtier directement. Ces tests portent sur l'agrégation (pure, sans
fastapi, testable partout) et sur l'invariant qui la rend possible : elle ne construit
JAMAIS le snapshot.

Ce qui est épinglé :
    1. ABSENT n'est pas ZÉRO — un courtier muet ne vaut pas 0 $, il rend le total
  INCOMPLET
     et il est NOMMÉ ;
  2. un courtier non configuré n'est pas un incident ;
  3. une position que le courtier ne chiffre pas ne DISPARAÎT pas du portefeuille ;
  4. le résumé ne publie jamais un total partiel comme un total ;
  5. la route ne touche ni `_snap`, ni `build_snapshot`.
"""

from __future__ import annotations

import ast
from pathlib import Path

from apps.api.portefeuille import FRAICHEUR_S, agreger, message

RACINE = Path(__file__).resolve().parents[2]


def _compte(nom="Alpaca", *, ok=True, equity=100.0, positions=None,
            configure=True, error=None):
    return {"nom": nom, "configure": configure, "ok": ok, "equity": equity,
            "positions": positions if positions is not None else [], "error": error}


def _pos(sym="AAPL", valeur=1000.0, pnl=10.0):
    return {"symbol": sym, "qty": 5, "last": 200.0, "market_value": valeur,
            "pnl": pnl, "pnl_pct": 0.01}


# --- 1. ABSENT n'est pas ZÉRO ----------------------------------------------

def test_deux_comptes_lus_donnent_un_total_COMPLET():
    p = agreger([_compte("Alpaca", equity=100.0, positions=[_pos()]),
                 _compte("Binance", equity=50.0, positions=[_pos("BTC", 20.0, 1.0)])])
    assert p["complet"] is True and p["equity_total"] == 150.0
    assert p["n_positions"] == 2 and p["incidents"] == []


def test_un_courtier_MUET_rend_le_total_INCOMPLET_et_est_NOMME():
    """Un total qui rétrécit en silence parce qu'un courtier ne répond plus ressemble
    trait pour trait à une perte. C'est le chiffre le plus dangereux du site."""
    p = agreger([_compte("Alpaca", equity=100.0, positions=[_pos()]),
                 _compte("Binance", ok=False, error="timeout")])
    assert p["complet"] is False
    assert p["equity_total"] == 100.0            # la part connue, PAS 100 + 0
    assert p["incidents"] == ["Binance : timeout"]
    binance = [c for c in p["comptes"] if c["nom"] == "Binance"][0]
    assert binance["equity"] is None and binance["n_positions"] is None
    assert binance["motif"] == "timeout"


def test_un_courtier_muet_SANS_motif_en_reçoit_un():
    p = agreger([_compte("Alpaca", ok=False, error=None)])
    assert p["incidents"] == ["Alpaca : sans réponse"]


# --- 2. non configuré ≠ incident -------------------------------------------

def test_un_compte_NON_CONFIGURE_est_hors_perimetre_pas_un_incident():
    p = agreger([_compte("Alpaca", equity=100.0, positions=[_pos()]),
                 _compte("Binance", configure=False, ok=False,
                         error="clés absentes (.env)")])
    assert p["complet"] is True and p["incidents"] == []
    assert [c["nom"] for c in p["comptes"]] == ["Alpaca"]


def test_aucun_courtier_lisible_le_DIT():
    p = agreger([_compte("Alpaca", ok=False, error="401")])
    assert p["disponible"] is False
    assert "indisponible" in message(p) and "401" in message(p)


# --- 3. une position non chiffrée ne disparaît pas --------------------------

def test_une_position_SANS_valeur_est_listee_exclue_du_total_et_citee():
    p = agreger([_compte(positions=[_pos("AAPL", 1000.0), _pos("ZZZ", None, None)])])
    assert p["n_positions"] == 2                       # elle EXISTE toujours
    assert p["valeur_positions"] == 1000.0         # mais ne pèse pas 0 dans le total
    assert p["sans_valeur"] == ["ZZZ"]
    assert "ZZZ" in message(p)


def test_aucune_valeur_connue_rend_None_jamais_zero():
    """Un 0,00 $ se lit comme une mesure. Une absence, non."""
    p = agreger([_compte(equity=None, ok=True, positions=[_pos("ZZZ", None, None)])])
    assert p["valeur_positions"] is None and p["equity_total"] is None


def test_les_positions_sont_triees_par_valeur_decroissante():
    p = agreger([_compte(positions=[_pos("A", 10.0), _pos("B", 900.0),
                                    _pos("C", 100.0)])])
    assert [r["symbole"] for r in p["positions"]] == ["B", "C", "A"]


def test_chaque_ligne_porte_son_compte_d_origine():
    p = agreger([_compte("Alpaca", positions=[_pos("AAPL")]),
                 _compte("Binance", positions=[_pos("BTC", 5.0)])])
    assert {r["symbole"]: r["compte"] for r in p["positions"]} == {
        "AAPL": "Alpaca", "BTC": "Binance"}


# --- 4. le résumé ne ment pas par omission ---------------------------------

def test_le_resume_d_un_total_COMPLET_ne_crie_pas_a_l_incomplet():
    m = message(agreger([_compte(equity=100.0, positions=[_pos()])]))
    assert "INCOMPLET" not in m and "1 position(s)" in m


def test_le_resume_d_un_total_PARTIEL_le_dit_et_nomme_le_manquant():
    m = message(agreger([_compte("Alpaca", equity=100.0, positions=[_pos()]),
                         _compte("Binance", ok=False, error="timeout")]))
    assert "TOTAL INCOMPLET" in m and "Binance" in m


# --- 5. l'invariant qui rend la route possible ------------------------------

def _corps(nom: str) -> str:
    src = (RACINE / "apps" / "api" / "main.py").read_text(encoding="utf-8")
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            corps = list(n.body)
            if (corps and isinstance(corps[0], ast.Expr)
                    and isinstance(corps[0].value, ast.Constant)):
                corps = corps[1:]          # la docstring a le DROIT de citer `_snap`
            return "\n".join(ast.unparse(x) for x in corps)
    raise AssertionError(f"{nom} introuvable dans apps/api/main.py")


def test_la_route_ne_construit_JAMAIS_le_snapshot():
    """C'est tout l'intérêt : `_snap()` coûte 30 à 60 s, ce qui interdirait un
    rafraîchissement toutes les 30 s. Ce test tombe si quelqu'un l'y rebranche."""
    for nom in ("portefeuille", "_lire_courtiers", "_compte_courtier"):
        code = _corps(nom)
        assert "_snap" not in code, f"{nom} touche au snapshot"
        assert "build_snapshot" not in code, f"{nom} construit le snapshot"


def test_la_route_ne_lit_que_equity_et_les_positions():
    """Le snapshot fait cinq appels par courtier (ordres, historique, OHLCV…). Les
    rajouter ici rendrait la route trop lourde pour son propre rythme."""
    code = _corps("_compte_courtier")
    for lourd in ("orders(", "open_orders(", "portfolio_history(", "ohlcv("):
        assert lourd not in code, f"_compte_courtier appelle {lourd}"
    assert "equity()" in code and "positions_detailed()" in code


def test_la_fraicheur_est_bornee_et_partagee():
    """Sans cache partagé, dix onglets ouverts feraient dix fois les appels courtier."""
    assert 5.0 <= FRAICHEUR_S <= 60.0
    code = _corps("portefeuille")
    assert "FRAICHEUR_S" in code and "_PF_CACHE" in code
