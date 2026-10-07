"""Non-régression du chemin d'ordres : `_reconcile` rend EXACTEMENT ce qu'il rendait.

Le découpage de `_reconcile` (233 lignes, audit du 06/10) ne doit changer aucune
décision. Ce test rejoue cinq comptes factices couvrant chaque branche — achat,
allègement, solde en quantité, non négociable, portail qui réduit et qui refuse,
géométrie swing manquante, séance fermée, rejet et panne du courtier, aperçu,
réduction de risque, sleeve protégée — et compare TOUT ce qui sort : texte affiché,
valeurs rendues, appels au courtier (identifiant client compris), compteurs des
garde-fous, alertes. La référence a été enregistrée AVANT le découpage
(`GOLDEN_ECRIRE=1` la régénère — seulement pour un changement VOULU).
"""

import importlib.util
import json
import os
import pathlib
import uuid
from datetime import datetime

import pytest

RACINE = pathlib.Path(__file__).resolve().parents[2]
REFERENCE = RACINE / "tests" / "execution" / "golden" / "reconcile.json"


def _run_live():
    spec = importlib.util.spec_from_file_location("run_live_golden",
                                                  RACINE / "scripts" / "run_live.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class _Rep:
    def __init__(self, status, id_="o-1"):
        self.status, self.id = status, id_


class Courtier:
    def __init__(self, rejets=(), pannes=()):
        self.appels, self.rejets, self.pannes = [], set(rejets), set(pannes)

    def submit_notional(self, sym, side, montant, client_id=None):
        self.appels.append(["notional", sym, str(side), round(montant, 4), client_id])
        if sym in self.pannes:
            raise ConnectionError(f"timeout {sym}")
        return _Rep("rejected" if sym in self.rejets else "accepted", f"id-{sym}")

    def close_position(self, sym):
        self.appels.append(["close", sym])
        return True


class Alertes:
    def __init__(self):
        self.vues = []

    def emit(self, a):
        self.vues.append([a.kind, str(a.severity), a.message, a.dedup_key])


def _c(sym, poids, **kw):
    return {"symbol": sym, "broker_symbol": sym, "weight_pct": poids,
            "capital": "alpaca", "asset_class": "equity", "tradeable": True, **kw}


CIBLES = [
    _c("AAA", 0.10, rank_score=1.5, strategy="preset"),
    _c("BBB", 0.05),
    _c("CCC", 0.02),
    _c("EEE", 0.05, tradeable=False),
    _c("FFF", 0.50),
    _c("GGG", 0.04, strategy="swing", entry=10.0),
    _c("QQQ", 0.06, asset_class="etf"),
    {"symbol": "BTC/USD", "broker_symbol": "BTC/USD", "weight_pct": 0.30,
     "capital": "bitmart", "asset_class": "crypto", "tradeable": True},
]
DETENU = {"BBB": 2000.0, "CCC": 8000.0, "DDD": 3000.0}


def _scenarios():
    return {
        "reel": dict(dry=False, reduce=1.0, rejets=(), pannes=()),
        "rejet_et_panne": dict(dry=False, reduce=1.0, rejets=("AAA",), pannes=("BBB",)),
        "apercu": dict(dry=True, reduce=1.0, rejets=(), pannes=()),
        "reduction": dict(dry=False, reduce=0.5, rejets=(), pannes=(),
                          proteger={"DDD"}, liquider_hors_cible=True),
        "sleeve": dict(dry=False, reduce=1.0, rejets=(), pannes=(),
                       liquider_hors_cible=False),
        "seance_fermee": dict(dry=False, reduce=1.0, rejets=(), pannes=(),
                              fermee=True),
    }


def _jouer(nom, sc, monkeypatch, capsys):
    from packages.execution import market_calendar as mc
    from packages.execution.garde_fous import Collecteur
    monkeypatch.setattr(uuid, "uuid4", lambda: uuid.UUID(int=7))
    if sc.get("fermee"):
        monkeypatch.delenv("QUANT_IGNORE_SESSION", raising=False)
        monkeypatch.setattr(mc, "feries_a_jour", lambda: True)
        monkeypatch.setattr(mc, "is_open", lambda ts=None, asset_class="equity":
                            asset_class == "crypto")
        monkeypatch.setattr(mc, "raison_fermeture", lambda asset_class=None: "fermé")
        ouverture = datetime(2026, 10, 7, 9)
        monkeypatch.setattr(mc, "prochaine_ouverture", lambda *a, **k: ouverture)
    rl = _run_live()
    alp, bit = Courtier(sc["rejets"], sc["pannes"]), Courtier()
    brokers = [("Alpaca", None if sc["dry"] else alp, 100_000.0, dict(DETENU)),
               ("Bitmart", None if sc["dry"] else bit, 10_000.0, {"BTCUSD": 1000.0})]
    obs, al = Collecteur(), Alertes()
    capsys.readouterr()
    sent, opened, sold = rl._reconcile(
        CIBLES, brokers, sc["reduce"], al, sc["dry"], obs,
        proteger=sc.get("proteger"),
        liquider_hors_cible=sc.get("liquider_hors_cible", True))
    gardes = {k: {**vars(g), "motifs": dict(sorted(g.motifs.items()))}
              for k, g in sorted(obs.gardes.items())}
    return {"sortie": capsys.readouterr().out, "sent": sent, "opened": opened,
            "sold": sold, "alpaca": alp.appels, "bitmart": bit.appels,
            "gardes": gardes, "alertes": al.vues}


@pytest.fixture
def _env(monkeypatch):
    for k in [k for k in os.environ if k.startswith("QUANT_")]:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("QUANT_IGNORE_SESSION", "1")
    monkeypatch.setenv("QUANT_MIN_POSITION", "100")
    monkeypatch.setenv("QUANT_RISK_MAX_ORDER_PCT", "0.15")
    monkeypatch.setenv("QUANT_RISK_MAX_WEIGHT", "0.20")
    monkeypatch.setenv("QUANT_RISK_MAX_GROSS", "1.00")
    monkeypatch.setenv("QUANT_RISK_MAX_POSITIONS", "6")


def test_reconcile_identique_a_la_reference(_env, monkeypatch, capsys):
    obtenu = {}
    for nom, sc in _scenarios().items():
        with monkeypatch.context() as mp:
            obtenu[nom] = json.loads(json.dumps(_jouer(nom, sc, mp, capsys),
                                                default=str))
    if os.environ.get("GOLDEN_ECRIRE") == "1":
        REFERENCE.parent.mkdir(parents=True, exist_ok=True)
        REFERENCE.write_text(json.dumps(obtenu, ensure_ascii=False, indent=1),
                             encoding="utf-8")
    attendu = json.loads(REFERENCE.read_text(encoding="utf-8"))
    for nom in attendu:
        assert obtenu[nom] == attendu[nom], nom


def test_la_reference_couvre_chaque_branche():
    ref = json.loads(REFERENCE.read_text(encoding="utf-8"))
    texte = "".join(s["sortie"] for s in ref.values())
    for marque in ("▲ achat", "▼ vente", "SOLDE (quantité)", "non négociable",
                   "REFUSÉ par le portail", "reject_missing_geometry", "REPORTÉ",
                   "ÉCHEC après retries", "REFUSÉ(S) par le courtier", "aperçu"):
        assert marque in texte, marque
