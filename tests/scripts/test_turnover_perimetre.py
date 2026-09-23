"""La rotation se mesure sur ce que le ROBOT a fait, pas sur ce qui porte des features.

TROISIÈME OCCURRENCE du défaut nommé par l'ADR-0188, et la plus coûteuse : celle-ci
rendait la mesure IMPOSSIBLE sans que rien ne le signale. `scripts/turnover_audit.py`
lisait `all(legacy=False)`. Or depuis la reconstruction du journal depuis les fills du
courtier (18/09), presque tous les lots sont `legacy=1` — mesuré sur le compte réel le
23/09 : 609 lots au périmètre ROBOT, dont QUATRE en `legacy=0`.

L'audit voyait donc UNE position fermée sur 578. Il aurait rendu soit `UNCALIBRATED`,
soit un taux de rotation calculé sur une seule ligne — avec toutes les apparences d'une
mesure, ce qui est pire.

Ce que ces tests épinglent :
  1. le script filtre sur l'ORIGINE, plus jamais sur `legacy` ;
  2. un lot rejoué du courtier (`R-`, legacy=1) ENTRE dans la mesure ;
  3. un import de provenance inconnue (`LEG-`) en est écarté ET compté ;
  4. le périmètre est ANNONCÉ, pour qu'un écart se voie sans relire le code.
"""
from __future__ import annotations

import ast
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
SCRIPT = (RACINE / "scripts" / "turnover_audit.py").read_text(encoding="utf-8")


def _code_sans_commentaires(src: str) -> str:
    """On ne juge que le CODE : un commentaire a le droit de nommer la règle qu'il
    explique — c'est même souhaitable, et c'est ce que fait ce script."""
    return "\n".join(l for l in src.splitlines()
                     if not l.lstrip().startswith("#"))


def test_le_script_ne_filtre_PLUS_sur_legacy():
    code = _code_sans_commentaires(SCRIPT)
    assert "legacy=False" not in code, (
        "le filtre `legacy` est revenu : la rotation se mesurerait sur 4 lots sur 609")


def test_le_script_filtre_sur_l_ORIGINE():
    code = _code_sans_commentaires(SCRIPT)
    assert "pris_par_le_robot" in code and "all()" in code


def test_le_script_ANNONCE_le_perimetre_qu_il_mesure():
    """Un périmètre tu se découvre en comparant deux chiffres qu'on n'a pas côte à côte."""
    assert "Périmètre" in SCRIPT and "hors périmètre" in SCRIPT


def test_le_script_reste_analysable_et_sans_import_d_execution():
    """La rotation est une mesure de recherche : elle ne doit rien importer du chemin
    d'ordre au-delà du module de périmètre, qui est une pure classification."""
    arbre = ast.parse(SCRIPT)
    modules = {n.module for n in ast.walk(arbre) if isinstance(n, ast.ImportFrom) and n.module}
    interdits = {m for m in modules
                 if m.startswith("packages.execution")
                 and m != "packages.execution.perimetre_journal"}
    assert not interdits, f"imports d'exécution interdits : {interdits}"


# --- le comportement, pas seulement la source -------------------------------

def _lot(ident: str, sym: str = "AAA"):
    from datetime import datetime, timezone

    from packages.core.models import AssetClass, Side, TradeRecord
    e = datetime(2026, 9, 1, tzinfo=timezone.utc)
    s = datetime(2026, 9, 5, tzinfo=timezone.utc)
    return TradeRecord(
        id=ident, instrument=sym, asset_class=AssetClass.EQUITY, venue="Alpaca",
        side=Side.LONG, qty=10.0, entry_ts=e, entry_price=100.0, avg_price=100.0,
        exit_ts=s, exit_price=110.0, pnl_pct=0.10, pnl_net=100.0, is_win=True,
        duration_s=4 * 86400.0, fees=1.0, fees_source="estimated",
        entry_reason="test", exit_reason="test")


def test_un_lot_REJOUE_du_courtier_entre_dans_la_mesure():
    """`R-…` vaut `legacy=1` et c'est exact — il n'a pas de features. Mais il décrit
    bien un aller-retour du robot, donc il compte dans la rotation."""
    from packages.execution.perimetre_journal import pris_par_le_robot
    for prefixe in ("R-20260918-Alpaca-AAA-1", "C-AAA-a1b2c3", "P-20260901-Alpaca-AAA"):
        assert pris_par_le_robot(prefixe), prefixe


def test_un_import_de_provenance_inconnue_reste_ecarte():
    from packages.execution.perimetre_journal import pris_par_le_robot
    assert not pris_par_le_robot("LEG-5fb0df0f4921")
    assert not pris_par_le_robot("X-9000")


def test_l_audit_tourne_sur_des_lots_sans_features():
    """La preuve que le filtre n'écartait pas des données inutilisables : `auditer`
    rend un résultat complet sur des lots qui n'ont aucun `features_snapshot`."""
    from packages.research.turnover_audit import auditer
    r = auditer([_lot("R-1", "AAA"), _lot("R-2", "BBB"), _lot("P-3", "CCC")])
    assert r.n_positions == 3 and r.n_fermetures == 3
