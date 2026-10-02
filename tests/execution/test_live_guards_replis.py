"""Kill-switch drawdown : les REPLIS qu'aucun test ne parcourait (77 % au 02/10).

Le seuil vient de `config/risk.yaml` (source de vérité, #425). Ce qui se passe quand ce
fichier est absent, mal formé ou faux décide si le kill-switch protège encore le compte.
Ces tests épinglent aussi ce que le kill-switch ÉMET quand il coupe (bus + alerte
CRITIQUE), et qu'un contrôle qui plante laisse passer le run sans le bloquer — en le
disant au témoin des garde-fous.
"""

import pytest

from packages.execution import live_guards as lg
from packages.execution.garde_fous import ERREUR, KILL_DD, Collecteur


@pytest.fixture(autouse=True)
def _sans_env(monkeypatch):
    monkeypatch.delenv("QUANT_INTRADAY_DD", raising=False)


@pytest.mark.parametrize("contenu", [
    "",                                                   # vide
    "- une\n- liste\n",                                   # pas un dict
    "portfolio: 3\n",                                     # portfolio pas un dict
    "portfolio:\n  max_daily_drawdown_pct: abc\n",        # non numérique
    "portfolio:\n  max_daily_drawdown_pct: 0\n",          # nul
    "portfolio:\n  max_daily_drawdown_pct: -0.2\n",       # négatif
])
def test_un_risk_yaml_inexploitable_retombe_sur_5_pct(tmp_path, contenu):
    f = tmp_path / "risk.yaml"
    f.write_text(contenu, encoding="utf-8")
    assert lg._dd_limit_depuis_yaml(f) == lg.DD_LIMIT_DEFAUT == -0.05


def test_un_risk_yaml_absent_retombe_sur_5_pct(tmp_path):
    assert lg._dd_limit_depuis_yaml(tmp_path / "absent.yaml") == -0.05


def test_la_magnitude_positive_du_yaml_devient_un_seuil_negatif(tmp_path):
    f = tmp_path / "risk.yaml"
    f.write_text("portfolio:\n  max_daily_drawdown_pct: 0.08\n", encoding="utf-8")
    assert lg._dd_limit_depuis_yaml(f) == pytest.approx(-0.08)


def test_le_vrai_risk_yaml_du_depot_vaut_moins_5_pct():
    assert lg._dd_limit_depuis_yaml() == pytest.approx(-0.05)


def test_une_variable_d_env_illisible_retombe_sur_le_yaml(monkeypatch):
    monkeypatch.setenv("QUANT_INTRADAY_DD", "cinq pour cent")
    assert lg.resolve_intraday_dd_limit() == pytest.approx(-0.05)


@pytest.fixture
def historique(monkeypatch, tmp_path):
    import packages.execution.equity_history as eh
    monkeypatch.setattr(eh, "_F", tmp_path / "eq.json")
    eh.record({"alpaca": 100_000.0}, today="2026-01-01")
    return eh


class Bus:
    def __init__(self):
        self.messages = []

    def publish(self, topic, payload):
        self.messages.append((topic, payload))


class Alertes:
    def __init__(self):
        self.alertes = []

    def emit(self, alerte):
        self.alertes.append(alerte)


def test_une_coupure_publie_sur_le_bus_et_leve_une_alerte_critique(historique):
    from packages.alerts import Severity
    from packages.common.event_bus import Topic
    bus, alertes, obs = Bus(), Alertes(), Collecteur()
    assert lg.dd_kill_switch(90_000.0, bus, alertes, obs) == 0.0
    assert bus.messages == [(Topic.KILL_SWITCH, {"drawdown": -0.1})]
    (a,) = alertes.alertes
    assert a.severity is Severity.CRITICAL and "drawdown" in a.message
    assert obs.rapport()[KILL_DD]["declenchements"] == 1


def test_un_controle_qui_plante_laisse_passer_et_le_dit(monkeypatch, historique):
    import packages.portfolio.stress as stress

    def panne(*a, **k):
        raise RuntimeError("calcul impossible")
    monkeypatch.setattr(stress, "drawdown_breach", panne)
    obs = Collecteur()
    assert lg.dd_kill_switch(50_000.0, None, None, obs) == 1.0   # ne BLOQUE pas le run
    assert obs.rapport()[KILL_DD]["etat"] == ERREUR               # mais le dit


def test_fail_loud_survit_a_un_moteur_d_alertes_en_panne(capsys):
    class AlertesCassees:
        def emit(self, alerte):
            raise ConnectionError("telegram muet")
    with pytest.raises(SystemExit) as exc:
        lg.fail_loud(["broker mort"], AlertesCassees(), code=3)
    assert exc.value.code == 3 and "broker mort" in capsys.readouterr().out


def test_fail_loud_emet_une_alerte_critique():
    from packages.alerts import Severity
    alertes = Alertes()
    with pytest.raises(SystemExit):
        lg.fail_loud(["a", "b"], alertes, code=4)
    (a,) = alertes.alertes
    assert a.severity is Severity.CRITICAL and "a · b" in a.message


def test_live_bitmart_cles_presentes_equity_nulle_est_fatal():
    class BitmartMort:
        def equity(self):
            return 0.0

        def _live(self):
            return True

    class AlpacaOk:
        def equity(self):
            return 1000.0
    alp, bit, _, bit_cap, fatal = lg.vet_brokers(AlpacaOk(), BitmartMort(), False, None)
    assert bit is None and bit_cap == 0.0
    assert any("Bitmart" in m for m in fatal)
