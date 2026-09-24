"""Une moyenne non pondérée ne décrit pas un compte.

Le 23/09, la première mesure réelle de rotation a rendu **+1,59 % par position sur 542
positions** — alors que le compte n'avait réalisé que **818,67 $**. Avec des lignes de
l'ordre de 5 000 $, ces deux nombres diffèrent d'un facteur cinquante.

La cause : `sum(pnls) / len(pnls)` traitait une fraction d'action soldée à +40 % sur
trois dollars exactement comme une ligne de 5 000 $ à +0,2 %. La poussière du
rebalancement dominait la moyenne. Le chiffre n'était pas faux — il décrivait une
population de lots, pas un portefeuille — et rien ne le disait.

Ce que ces tests épinglent :
  1. le poids est un MONTANT, jamais une quantité ;
  2. sans notionnel lisible, on rend None — jamais 0, qui se lirait comme une mesure ;
  3. les deux moyennes sont publiées, car leur ÉCART est le diagnostic ;
  4. leur rapport est une MESURE, toujours publiée — aucun seuil inventé ne
     décide de ce qui est dit, et une pondérée nulle ne fait pas taire le
     diagnostic : zéro est l'écart maximal, pas son absence.
"""
from __future__ import annotations

from datetime import UTC, datetime

from packages.core.models import AssetClass, Side, TradeRecord
from packages.research.turnover_audit import auditer, rapport

E = datetime(2026, 9, 1, tzinfo=UTC)
S = datetime(2026, 9, 3, tzinfo=UTC)


def _lot(ident: str, qty: float, prix: float, pnl_pct: float) -> TradeRecord:
    return TradeRecord(
        id=ident, instrument=ident[:4], asset_class=AssetClass.EQUITY, venue="Alpaca",
        side=Side.LONG, qty=qty, entry_ts=E, entry_price=prix, avg_price=prix,
        exit_ts=S, exit_price=prix * (1 + pnl_pct), pnl_pct=pnl_pct,
        pnl_net=qty * prix * pnl_pct, is_win=pnl_pct > 0,
        duration_s=2 * 86400.0, entry_reason="t", exit_reason="rebalancement")


def test_la_poussiere_ne_domine_plus_la_moyenne():
    """LE cas du 23/09 : une miette à +40 % sur 3 $, une vraie ligne à +0,2 % sur
    5 000 $."""
    a = auditer([_lot("P-miette", qty=1.0, prix=3.0, pnl_pct=0.40),
                 _lot("P-ligne", qty=10.0, prix=500.0, pnl_pct=0.002)])
    # non pondérée : (40 % + 0,2 %) / 2 ≈ +20 %
    assert abs(a.rendement_moyen_pct - 0.201) < 1e-3
    # pondérée par 3 $ contre 5 000 $ : écrasée vers la vraie ligne
    assert abs(a.rendement_pondere_pct - 0.0022) < 1e-3
    assert a.notionnel_total == 5003.0


def test_le_poids_est_un_MONTANT_pas_une_QUANTITE():
    """1 000 actions à 3 $ engagent six fois moins que 5 actions à 500 $. Pondérer par
    la quantité aurait inversé le rapport de force."""
    a = auditer([_lot("P-nombreuses", qty=1000.0, prix=3.0, pnl_pct=0.10),
                 _lot("P-cheres", qty=5.0, prix=500.0, pnl_pct=0.00)])
    # notionnels : 3 000 $ contre 2 500 $ → proches, donc moyenne proche de la simple
    assert abs(a.rendement_pondere_pct - 0.0545) < 1e-3
    # une pondération par la QUANTITÉ aurait donné ~0,0995 (1000 contre 5)
    assert a.rendement_pondere_pct < 0.07


def test_sans_notionnel_lisible_on_rend_None_et_non_zero():
    """Un zéro se lit comme une mesure ; une absence doit se lire comme absente."""
    a = auditer([_lot("P-a", qty=10.0, prix=0.0, pnl_pct=0.05)])
    assert a.rendement_pondere_pct is None and a.notionnel_total in (0.0, None)
    assert a.rendement_moyen_pct is not None      # la moyenne simple, elle, existe


def test_les_positions_sans_montant_sont_ECARTEES_pas_comptees_a_zero():
    """Les compter à poids nul reviendrait à les inclure avec un avis silencieux
    qu'elles ne pèsent rien."""
    a = auditer([_lot("P-sans", qty=10.0, prix=0.0, pnl_pct=0.90),
                 _lot("P-avec", qty=10.0, prix=100.0, pnl_pct=0.01)])
    # la miette sans prix n'entre pas dans la pondération
    assert abs(a.rendement_pondere_pct - 0.01) < 1e-9


def test_le_rapport_publie_LES_DEUX_moyennes():
    """Publier l'une sans l'autre laisse lire une performance que le capital n'a
    pas vue."""
    txt = rapport(auditer([_lot("P-miette", 1.0, 3.0, 0.40),
                           _lot("P-ligne", 10.0, 500.0, 0.002)]))
    assert "NON pondéré" in txt and "PONDÉRÉ par le montant engagé" in txt


def test_les_deux_moyennes_et_leur_rapport_sont_TOUJOURS_publies():
    """Le rapport entre deux moyennes est une MESURE, pas un verdict conditionnel."""
    txt = rapport(auditer([_lot("P-miette", 1.0, 3.0, 0.40),
                           _lot("P-ligne", 10.0, 500.0, 0.002)]))
    assert "PONDÉRÉ est comparable au réalisé du compte" in txt
    assert "rapport" in txt


def test_aucun_seuil_invente_ne_decide_de_ce_qui_est_dit():
    """Un seuil non mesuré sur la base réelle ne doit gouverner aucune affirmation.

    La première version ne parlait qu'au-delà d'un facteur 3 entre les deux moyennes,
    et affirmait alors que « la performance vient des PETITES lignes ». Ce 3 sortait de
    nulle part. Le dépôt exige qu'un seuil vienne de la base ou s'écrive UNCALIBRATED :
    les deux chiffres se publient donc toujours, et l'écart n'est pas qualifié.
    """
    nuance = rapport(auditer([_lot("P-a", 10.0, 100.0, 0.05),
                              _lot("P-b", 10.0, 120.0, 0.04)]))
    nature = rapport(auditer([_lot("P-miette", 1.0, 3.0, 0.40),
                              _lot("P-ligne", 10.0, 500.0, 0.002)]))
    for txt in (nuance, nature):
        assert "UNCALIBRATED" in txt
        assert "PETITES lignes" not in txt, "un verdict inventé est réapparu"


def test_une_ponderee_NULLE_ne_fait_pas_taire_le_diagnostic():
    """Zéro n'est pas « pas d'écart » : c'est l'écart maximal, et il faut le DIRE.

    Un garde-fou anti-division rendait une liste vide quand la pondérée valait 0,00 %.
    Une miette à +40 % compensée par une grosse ligne à peine négative produit
    exactement ce cas — le plus parlant des deux, et le seul qui restait muet.
    """
    a = auditer([_lot("P-miette", 1.0, 3.0, 0.40),
                 _lot("P-ligne", 10.0, 500.0, -0.00024)])
    assert abs(a.rendement_pondere_pct) < 1e-9, a.rendement_pondere_pct
    txt = rapport(a)
    assert "écart maximal, pas absence d'écart" in txt
    assert "UNCALIBRATED" in txt


def test_les_deux_moyennes_coincident_quand_les_lignes_sont_egales():
    """Garde-fou du test lui-même : sans dispersion des montants, rien ne diverge."""
    a = auditer([_lot("P-a", 10.0, 100.0, 0.10), _lot("P-b", 10.0, 100.0, -0.02)])
    assert abs(a.rendement_moyen_pct - a.rendement_pondere_pct) < 1e-9


def test_le_MEME_nombre_s_ecrit_PAREIL_a_deux_endroits_du_rapport():
    """Le 24/09, la 1re sortie réelle annonçait « +0,02 % » deux lignes sous
    « +1,59 % » — la même quantité, écrite cent fois trop petit.

    Ces champs sont des FRACTIONS (0,0159) ; le bloc d'écart les rendait bruts quand
    tout le reste du rapport les convertit. Le rapport entre les deux, lui, restait
    juste — les unités s'annulent —, si bien que rien dans la sortie ne départageait
    les deux versions du même nombre. Le lecteur n'avait aucune raison de croire
    l'une plutôt que l'autre.

    Ce test ne vérifie pas un format : il vérifie qu'UNE quantité n'a qu'UNE écriture.
    """
    a = auditer([_lot("P-miette", 1.0, 3.0, 0.40), _lot("P-ligne", 10.0, 500.0, 0.002)])
    txt = rapport(a)
    simple = f"{a.rendement_moyen_pct * 100:+.2f} %"
    pondere = f"{a.rendement_pondere_pct * 100:+.2f} %"
    assert f"Rendement moyen par position (NON pondéré) : {simple}" in txt
    assert f"Moyenne simple {simple} · PONDÉRÉE par le notionnel {pondere}" in txt
    # et la version cent fois trop petite n'est nulle part
    assert f"{a.rendement_moyen_pct:+.2f} %" not in txt
