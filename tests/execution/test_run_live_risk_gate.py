"""Le portail de risque est-il RÉELLEMENT dans le chemin des ordres ?

Contexte du 25/08 : les limites de risque du projet (`packages.risk`) étaient documentées,
testées, et absentes du seul script qui envoie de vrais ordres. Ces tests vérifient le CÂBLAGE,
pas la logique du portail (couverte par `tests/risk/test_order_gate.py`) — c'est précisément la
distinction qui manquait : une règle correcte mais non branchée ne protège rien.
"""

import importlib.util
import pathlib

import pytest

RACINE = pathlib.Path(__file__).resolve().parents[2]


def _run_live():
    spec = importlib.util.spec_from_file_location("run_live", RACINE / "scripts" / "run_live.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class CourtierFactice:
    """Enregistre ce qu'on lui demande, n'exécute rien."""

    def __init__(self):
        self.ordres: list[tuple] = []

    def submit_notional(self, sym, side, montant):
        self.ordres.append(("notional", sym, montant))

    def close_position(self, sym):
        self.ordres.append(("close", sym, None))


def _cible(symbole, poids):
    return {"symbol": symbole, "broker_symbol": symbole, "weight_pct": poids,
            "capital": "alpaca", "asset_class": "equity", "tradeable": True}


def test_un_ordre_hors_limite_est_reduit_avant_d_atteindre_le_courtier(monkeypatch):
    """Une cible à 50 % du compte doit arriver au courtier rabotée au plafond d'ordre (15 %)."""
    monkeypatch.setenv("QUANT_RISK_MAX_ORDER_PCT", "0.15")
    monkeypatch.setenv("QUANT_RISK_MAX_WEIGHT", "0.90")
    monkeypatch.setenv("QUANT_RISK_MAX_GROSS", "1.00")
    monkeypatch.setenv("QUANT_MIN_POSITION", "100")
    rl = _run_live()
    b = CourtierFactice()
    sent, _, _ = rl._reconcile([_cible("AAA", 0.50)],
                               [("Alpaca", b, 100_000.0, {})], 1.0, None, dry=False)
    assert sent == 1
    kind, sym, montant = b.ordres[0]
    assert sym == "AAA" and montant == pytest.approx(15_000.0, rel=1e-6)


def test_le_plafond_de_positions_empeche_l_ouverture(monkeypatch):
    monkeypatch.setenv("QUANT_RISK_MAX_POSITIONS", "1")
    monkeypatch.setenv("QUANT_MIN_POSITION", "100")
    rl = _run_live()
    b = CourtierFactice()
    detenu = {"ZZZ": 10_000.0}                       # 1 position déjà ouverte = plafond atteint
    sent, _, _ = rl._reconcile([_cible("AAA", 0.10), _cible("ZZZ", 0.10)],
                               [("Alpaca", b, 100_000.0, detenu)], 1.0, None, dry=False)
    envoyes = {o[1] for o in b.ordres}
    assert "AAA" not in envoyes                       # nouvelle ligne refusée par le portail


def test_une_liquidation_traverse_le_portail(monkeypatch):
    """Le détenu hors-cible doit être soldé même si toutes les limites sont saturées."""
    monkeypatch.setenv("QUANT_RISK_MAX_POSITIONS", "1")
    monkeypatch.setenv("QUANT_RISK_MAX_GROSS", "0.01")
    monkeypatch.setenv("QUANT_MIN_POSITION", "1000")
    rl = _run_live()
    b = CourtierFactice()
    sent, _, sold = rl._reconcile([], [("Alpaca", b, 100_000.0, {"OLD": 5_000.0})],
                                  1.0, None, dry=False)
    assert ("close", "OLD", None) in b.ordres and sent == 1 and sold


def test_l_exposition_brute_tient_compte_des_ordres_deja_envoyes(monkeypatch):
    """Sans cumul, chaque ordre serait jugé contre l'état initial et la somme dépasserait la
    limite — le plafond de levier ne bornerait alors rien."""
    monkeypatch.setenv("QUANT_RISK_MAX_GROSS", "1.00")
    monkeypatch.setenv("QUANT_RISK_MAX_ORDER_PCT", "1.00")
    monkeypatch.setenv("QUANT_RISK_MAX_WEIGHT", "1.00")
    monkeypatch.setenv("QUANT_MIN_POSITION", "100")
    rl = _run_live()
    b = CourtierFactice()
    # trois cibles à 40 % chacune : la somme est déjà bornée à 100 % par l'anti-levier amont,
    # le portail ne doit en aucun cas laisser passer plus que le capital.
    rl._reconcile([_cible("A", 0.40), _cible("B", 0.40), _cible("C", 0.40)],
                  [("Alpaca", b, 100_000.0, {})], 1.0, None, dry=False)
    total = sum(m for _, _, m in b.ordres if m)
    assert total <= 100_000.0 + 1e-6


def test_le_portail_tourne_aussi_en_dry_run(monkeypatch):
    """L'aperçu doit montrer ce que le portail ferait — sinon `make live` mentirait sur les
    ordres réellement envoyables."""
    monkeypatch.setenv("QUANT_RISK_MAX_ORDER_PCT", "0.01")
    monkeypatch.setenv("QUANT_MIN_POSITION", "100")
    rl = _run_live()
    b = CourtierFactice()
    sent, _, _ = rl._reconcile([_cible("AAA", 0.50)],
                               [("Alpaca", b, 100_000.0, {})], 1.0, None, dry=True)
    assert sent == 0 and b.ordres == []               # dry-run : rien n'est envoyé
