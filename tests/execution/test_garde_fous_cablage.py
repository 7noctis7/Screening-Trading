"""Les garde-fous alimentent-ils VRAIMENT le témoin, depuis le chemin de production ?

`tests/execution/test_garde_fous.py` vérifie que le témoin compte juste ; ici on vérifie
qu'il est BRANCHÉ — la distinction qui a déjà manqué une fois à ce dépôt, quand les
limites de risque étaient testées, documentées, et absentes du seul script qui envoie
des ordres.
"""

import ast
import importlib.util
import pathlib

import pytest

from packages.execution import garde_fous as gf
from packages.execution.live_guards import dd_kill_switch

RACINE = pathlib.Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _hors_calendrier(monkeypatch):
    monkeypatch.setenv("QUANT_IGNORE_SESSION", "1")


def _run_live():
    spec = importlib.util.spec_from_file_location("run_live", RACINE / "scripts" / "run_live.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class _Reponse:
    def __init__(self, status):
        self.status = status


class CourtierFactice:
    def __init__(self):
        self.ordres: list[tuple] = []

    def submit_notional(self, sym, side, montant):
        self.ordres.append((sym, montant))
        return _Reponse("accepted")

    def close_position(self, sym):
        self.ordres.append((sym, None))
        return True


def _cible(symbole, poids):
    return {"symbol": symbole, "broker_symbol": symbole, "weight_pct": poids,
            "capital": "alpaca", "asset_class": "equity", "tradeable": True}


def test_une_reduction_reelle_du_portail_arrive_au_temoin(monkeypatch):
    """Le chiffre doit être celui que le courtier a subi : 50 000 demandés, 15 000 partis."""
    monkeypatch.setenv("QUANT_RISK_MAX_ORDER_PCT", "0.15")
    monkeypatch.setenv("QUANT_RISK_MAX_WEIGHT", "0.90")
    monkeypatch.setenv("QUANT_MIN_POSITION", "100")
    rl, b, obs = _run_live(), CourtierFactice(), gf.Collecteur()
    rl._reconcile([_cible("AAA", 0.50)], [("Alpaca", b, 100_000.0, {})],
                  1.0, None, False, obs)
    r = obs.rapport()[gf.PORTAIL]
    assert r["observations"] == 1 and r["declenchements"] == 1
    assert r["effet_usd"] == pytest.approx(35_000.0)
    assert r["motifs"] == {"taille_ordre": 1}
    assert b.ordres[0][1] == pytest.approx(15_000.0)     # et l'ordre, lui, est bien réduit


def test_un_refus_du_portail_arrive_au_temoin(monkeypatch):
    monkeypatch.setenv("QUANT_RISK_MAX_POSITIONS", "1")
    monkeypatch.setenv("QUANT_MIN_POSITION", "100")
    rl, b, obs = _run_live(), CourtierFactice(), gf.Collecteur()
    rl._reconcile([_cible("AAA", 0.10), _cible("ZZZ", 0.10)],
                  [("Alpaca", b, 100_000.0, {"ZZZ": 10_000.0})], 1.0, None, False, obs)
    r = obs.rapport()[gf.PORTAIL]
    assert r["motifs"].get("max_positions") == 1
    assert r["effet_usd"] and r["effet_usd"] > 0
    assert "AAA" not in {o[0] for o in b.ordres}


def test_sans_temoin_le_chemin_d_ordre_est_inchange(monkeypatch):
    """Le témoin est OPTIONNEL : les appelants existants ne passent rien, et rien ne casse."""
    monkeypatch.setenv("QUANT_RISK_MAX_ORDER_PCT", "0.15")
    monkeypatch.setenv("QUANT_MIN_POSITION", "100")
    rl, b = _run_live(), CourtierFactice()
    sent, _, _ = rl._reconcile([_cible("AAA", 0.50)],
                               [("Alpaca", b, 100_000.0, {})], 1.0, None, dry=False)
    assert sent == 1 and b.ordres[0][1] == pytest.approx(15_000.0)


def _eq(monkeypatch, tmp_path, points: dict):
    import packages.execution.equity_history as eh
    monkeypatch.setattr(eh, "_F", tmp_path / "eq.json")
    for jour, v in points.items():
        eh.record({"alpaca": v}, today=jour)


def test_le_kill_switch_drawdown_distingue_ses_trois_1_point_0(monkeypatch, tmp_path):
    """Trois chemins rendent 1.0 — « rien à couper », « historique trop court » et
    « le contrôle a planté ». À l'écran ils se ressemblent ; au rapport, non."""
    _eq(monkeypatch, tmp_path, {"2026-01-01": 100_000.0})
    sain = gf.Collecteur()
    assert dd_kill_switch(97_000.0, None, None, sain) == 1.0
    assert sain.rapport()[gf.KILL_DD]["etat"] == gf.ACTIVE
    assert sain.rapport()[gf.KILL_DD]["declenchements"] == 0

    import packages.execution.equity_history as eh
    monkeypatch.setattr(eh, "_F", tmp_path / "vide.json")
    court = gf.Collecteur()
    assert dd_kill_switch(10_000.0, None, None, court) == 1.0
    assert court.rapport()[gf.KILL_DD]["etat"] == gf.UNCALIBRATED

    monkeypatch.setattr(eh, "_load", lambda: (_ for _ in ()).throw(RuntimeError("base KO")))
    casse = gf.Collecteur()
    assert dd_kill_switch(10_000.0, None, None, casse) == 1.0
    assert casse.rapport()[gf.KILL_DD]["etat"] == gf.ERREUR


def test_le_kill_switch_drawdown_compte_sa_coupure(monkeypatch, tmp_path):
    _eq(monkeypatch, tmp_path, {"2026-01-01": 100_000.0, "2026-01-02": 98_000.0})
    obs = gf.Collecteur()
    assert dd_kill_switch(80_000.0, None, None, obs) == 0.0
    r = obs.rapport()[gf.KILL_DD]
    assert r["declenchements"] == 1 and r["motifs"] == {"drawdown": 1}
    assert r["effet_usd"] is None      # une coupure d'exposition ne se chiffre pas en $


def test_le_disjoncteur_en_observation_enregistre_le_jour_ou_il_AURAIT_coupe(monkeypatch):
    """LA mesure qui manquait : `coupe_circuit` conditionne son armement à ces jours-là."""
    rl, obs = _run_live(), gf.Collecteur()
    import packages.execution.coupe_circuit as cc
    monkeypatch.setattr(cc, "evaluer", lambda e: {"disponible": True, "verrouille": True,
                                                  "agit": False, "motif": "perte 3,2 %",
                                                  "variation_jour": -3200.0,
                                                  "limite": -3000.0})
    assert rl._disjoncteur(100_000.0, obs) == 1.0        # OBSERVE, n'agit pas
    r = obs.rapport()[gf.DISJONCTEUR]
    assert r["aurait_declenche"] == 1 and r["declenchements"] == 0


def test_le_disjoncteur_en_panne_est_ERROR_et_le_run_continue(monkeypatch):
    rl, obs = _run_live(), gf.Collecteur()
    import packages.execution.coupe_circuit as cc
    monkeypatch.setattr(cc, "evaluer", lambda e: (_ for _ in ()).throw(RuntimeError("KO")))
    assert rl._disjoncteur(100_000.0, obs) == 1.0
    assert obs.rapport()[gf.DISJONCTEUR]["etat"] == gf.ERREUR


def test_la_garde_journaliere_compte_le_passage_refuse(monkeypatch):
    rl, obs = _run_live(), gf.Collecteur()
    import packages.execution.garde_journaliere as gj
    monkeypatch.setattr(gj, "evaluer", lambda f: {"deja_rebalance": True, "desarme": False,
                                                  "n": 1, "jour": "2026-09-20"})
    monkeypatch.setattr(gj, "message", lambda d: "déjà rebalancé")

    class _Br:
        def orders(self, limit=200):
            return []

    assert rl._deja_rebalance_aujourdhui((("Alpaca", _Br(), 0.0, {}),), obs) is True
    r = obs.rapport()[gf.GARDE_JOUR]
    assert r["declenchements"] == 1 and r["motifs"] == {"deja_rebalance": 1}


def test_le_portail_de_risque_reste_une_fonction_PURE():
    """Le témoin vit chez l'appelant, jamais dans la dernière barrière : une écriture
    disque dans `order_gate` créerait un monde où enregistrer une statistique fait
    échouer un ordre."""
    src = (RACINE / "packages" / "risk" / "order_gate.py").read_text()
    arbre = ast.parse(src)
    importes = {a.name.split(".")[0] for n in ast.walk(arbre)
                if isinstance(n, ast.Import) for a in n.names}
    importes |= {(n.module or "").split(".")[0] for n in ast.walk(arbre)
                 if isinstance(n, ast.ImportFrom)}
    assert "json" not in importes and "pathlib" not in importes
    assert not any(m.startswith("packages") for m in importes if m)
    appels = {n.func.id for n in ast.walk(arbre)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "open" not in appels and "print" not in appels


# --- GARDE DE SÉANCE (21/09) : le sixième filtre, trouvé en lisant un run réel.
# Le 21/09 à 08:54 ET, 19 lignes ont été reportées pour 52 596 $ avant même d'atteindre
# le portail — et rien ne le comptait. Un report qui revient chaque jour est un problème
# de PLANNING ; un report isolé est un jour férié. Sans compteur, les deux se ressemblent.

def _seance(monkeypatch, ouverte: bool):
    import packages.execution.market_calendar as mc
    monkeypatch.delenv("QUANT_IGNORE_SESSION", raising=False)
    monkeypatch.setattr(mc, "is_open", lambda asset_class=None: ouverte)
    monkeypatch.setattr(mc, "feries_a_jour", lambda: True)
    monkeypatch.setattr(mc, "raison_fermeture", lambda asset_class=None: "hors séance")


def test_un_ordre_reporte_hors_seance_est_compte_avec_son_notionnel(monkeypatch):
    monkeypatch.setenv("QUANT_MIN_POSITION", "100")
    _seance(monkeypatch, ouverte=False)
    rl, b, obs = _run_live(), CourtierFactice(), gf.Collecteur()
    sent, _, _ = rl._reconcile([_cible("AAA", 0.05)],
                               [("Alpaca", b, 100_000.0, {})], 1.0, None, False, obs)
    r = obs.rapport()[gf.SEANCE]
    assert sent == 0 and not b.ordres                  # rien n'est parti
    assert r["declenchements"] == 1
    assert r["effet_usd"] == pytest.approx(5_000.0)    # le montant NON envoyé
    assert r["motifs"] == {"equity": 1}                # le motif est la classe d'actif
    assert gf.PORTAIL not in obs.rapport()             # le portail n'est jamais atteint


def test_seance_ouverte_compte_une_observation_sans_declenchement(monkeypatch):
    monkeypatch.setenv("QUANT_MIN_POSITION", "100")
    _seance(monkeypatch, ouverte=True)
    rl, b, obs = _run_live(), CourtierFactice(), gf.Collecteur()
    rl._reconcile([_cible("AAA", 0.05)], [("Alpaca", b, 100_000.0, {})],
                  1.0, None, False, obs)
    r = obs.rapport()[gf.SEANCE]
    assert r["observations"] == 1 and r["declenchements"] == 0
    assert r["effet_usd"] == 0.0
    assert gf.PORTAIL in obs.rapport()                 # et le portail, lui, est atteint


def test_le_garde_de_seance_ignore_se_declare_DESARME(monkeypatch):
    """`QUANT_IGNORE_SESSION=1` est une échappatoire explicite : le rapport doit dire
    DÉSARMÉ, pas afficher un zéro qui se lirait « rien à signaler »."""
    monkeypatch.setenv("QUANT_IGNORE_SESSION", "1")
    monkeypatch.setenv("QUANT_MIN_POSITION", "100")
    rl, b, obs = _run_live(), CourtierFactice(), gf.Collecteur()
    rl._reconcile([_cible("AAA", 0.05)], [("Alpaca", b, 100_000.0, {})],
                  1.0, None, False, obs)
    assert obs.rapport()[gf.SEANCE]["etat"] == gf.DESARME
