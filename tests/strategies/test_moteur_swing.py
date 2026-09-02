"""Moteur swing : composition correcte, refus explicites, dimensionnement exact.

Ces classes ne calculent presque rien elles-mêmes ; ce qu'on teste ici, c'est donc la
COMPOSITION — l'ordre des filtres, ce qui est refusé, et surtout ce que le moteur fait
quand une donnée manque. C'est là que les garde-fous se contournent tout seuls.
"""

import math
from dataclasses import dataclass

from packages.risk.ddm import MachineDDM, ReglesDDM
from packages.strategies.moteur_swing import MarketStructureEngine, RiskManager


@dataclass
class B:
    open: float
    high: float
    low: float
    close: float
    volume: float


def _zigzag(n: int, base: float = 100.0, pente: float = 0.0, amp: float = 3.0):
    out = []
    for i in range(n):
        phase = i % 10
        p = base + pente * i + amp * (phase if phase <= 5 else 10 - phase)
        out.append(B(p, p + 1.0, p - 1.0, p, 1000.0))
    return out


def test_le_raffinement_1h_refuse_de_conclure_sans_donnee_intraday():
    """LE point à ne pas rater : sans barre 1H, la réponse n'est pas « prêt ».

    Renvoyer un feu vert par défaut ferait disparaître un filtre de la spec en silence —
    le système se comporterait comme s'il avait vérifié quelque chose.
    """
    m = MarketStructureEngine()
    r = m.raffiner_entree({"sens": "long"}, None)
    assert r["pret"] is False and r["indecidable"] is True
    assert "NON MESURABLE" in r["motif"]


def test_hurst_non_calculable_ne_devient_pas_un_refus_mesure():
    """Absence de mesure et mesure défavorable sont deux choses différentes."""
    r = MarketStructureEngine().persistance(_zigzag(30))
    assert r["disponible"] is False and r["autorise"] is False
    assert "indécidable" in r["motif"]


def test_aucune_proposition_avec_un_stop_du_mauvais_cote():
    """Un stop du mauvais côté donne une taille absurde, pas une erreur visible."""
    m = MarketStructureEngine()
    assert m._verifier("X", "SFP", "long", 100.0, 105.0, 130.0, {}) is None
    assert m._verifier("X", "SFP", "short", 100.0, 95.0, 70.0, {}) is None


def test_aucune_proposition_sous_le_rr_minimum():
    m = MarketStructureEngine(rr_min=3.0)
    assert m._verifier("X", "OTE", "long", 100.0, 98.0, 104.0, {}) is None   # RR 2
    assert m._verifier("X", "OTE", "long", 100.0, 98.0, 106.0, {}) is not None  # RR 3


def test_sfp_place_le_stop_derriere_la_meche_balayee():
    """L'invalidant du SFP est l'extrême que la mèche vient de prendre, pas un ATR."""
    bars = _zigzag(80)
    plancher = min(float(b.low) for b in bars[25:75])
    bars.append(B(plancher, plancher + 4, plancher - 6, plancher + 3, 9000.0))
    d = MarketStructureEngine().detecter("X", bars)
    assert d["sfp"]["sfp"] and d["sfp"]["sens"] == "long"
    p = d["propositions"][0]
    assert p["scenario"] == "SFP"
    assert p["stop"] < d["sfp"]["extreme"]         # sous la mèche, avec la marge d'ATR
    assert p["rr"] >= 3.0 - 1e-9


def test_la_taille_suit_exactement_capital_fois_r_sur_distance():
    """La formule de la spec, vérifiée au centime — pas approchée."""
    rm = RiskManager(MachineDDM(ReglesDDM(r_base=0.01)))
    d = rm.taille(100_000.0, {"entree": 100.0, "stop": 96.0})
    assert abs(d["quantite"] - 250.0) < 1e-9      # 1 000 $ de risque / 4 $ de distance
    assert abs(d["risque_pct"] - 0.01) < 1e-12


def test_le_facteur_de_regime_reduit_la_taille_et_donc_la_perte_au_stop():
    """Il multiplie la TAILLE, jamais R : la perte en cas de stop est bien divisée."""
    rm = RiskManager(MachineDDM(ReglesDDM(r_base=0.01)))
    plein = rm.taille(100_000.0, {"entree": 100.0, "stop": 96.0}, 1.0)
    bear = rm.taille(100_000.0, {"entree": 100.0, "stop": 96.0}, 0.5)
    assert abs(bear["quantite"] - plein["quantite"] / 2) < 1e-9
    assert abs(bear["risque_devise"] - plein["risque_devise"] / 2) < 1e-9


def test_quatre_pertes_font_descendre_le_niveau_et_diviser_la_taille():
    """La descente géométrique de la spec, bout à bout."""
    rm = RiskManager(MachineDDM(ReglesDDM(r_base=0.01)))
    avant = rm.taille(100_000.0, {"entree": 100.0, "stop": 96.0})["quantite"]
    for _ in range(4):
        rm.enregistrer_trade(-1.0)
    apres = rm.taille(100_000.0, {"entree": 100.0, "stop": 96.0})["quantite"]
    assert abs(apres - avant / 2) < 1e-9


def _closes(rends, base=100.0):
    out = [base]
    for r in rends:
        out.append(out[-1] * (1 + r))
    return out


def test_le_plan_coupe_par_correlation_et_dit_ce_qu_il_a_coupe():
    """Un plan qui n'affiche que ce qu'il garde rend ses propres règles invérifiables."""
    base = [0.012 * (-1) ** i + 0.0005 * i for i in range(40)]
    closes = {n: _closes([x * f for x in base])
              for n, f in (("A", 1.0), ("B", 1.01), ("C", 0.99), ("D", 1.02))}
    props = [{"symbole": s, "entree": 100.0, "stop": 96.0} for s in "ABCD"]
    ref = [300.0 - 0.5 * i for i in range(250)]            # marché sous sa MM200
    rm = RiskManager(MachineDDM(ReglesDDM(r_base=0.01)))
    plan = rm.plan(100_000.0, props, ref, closes, fenetre=30, maximum=3)
    assert plan["regime"] == "bear" and plan["facteur_long"] == 0.5
    assert [x["symbole"] for x in plan["lignes"]] == ["A", "B", "C"]
    assert [x["symbole"] for x in plan["refusees"]] == ["D"]
    assert math.isclose(plan["lignes"][0]["dimensionnement"]["quantite"], 125.0)
