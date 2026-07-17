"""Garde-fous d'exécution (audit 07/15) : inconnu ≠ zéro, brokers morts écartés,
kill-switch drawdown réel, fail-loud. Brokers factices — aucun réseau."""

import pytest

from packages.execution.live_guards import (current_values, dd_kill_switch,
                                            fail_loud, vet_brokers)


class _Ok:
    name = "ok"

    def positions_detailed(self):
        return [{"symbol": "AAPL", "market_value": 100}]

    def equity(self):
        return 1000.0

    def _live(self):
        return True


class _Boom(_Ok):
    name = "boom"

    def positions_detailed(self):
        raise RuntimeError("api positions down")


class _Dead(_Ok):
    name = "dead"

    def equity(self):
        return 0.0                                    # clé invalide / equity illisible


def test_positions_ko_donne_none_pas_zero():
    """CRITIQUE audit : lecture en échec ⇒ None (inconnu), jamais {} (détenu=0)."""
    cur_a, cur_b = current_values(_Boom(), _Ok())
    assert cur_a is None                              # broker en panne → inconnu
    assert cur_b == {"AAPL": 100.0}                   # broker sain → lu normalement


def test_broker_mort_ecarte_et_fatal():
    alp, bit, alp_cap, bit_cap, fatal = vet_brokers(_Dead(), None, dry=False, cli_equity=None)
    assert alp is None and alp_cap == 0.0 and fatal   # écarté + motif d'échec (run rouge)


def test_broker_sain_conserve():
    alp, bit, alp_cap, bit_cap, fatal = vet_brokers(_Ok(), None, dry=False, cli_equity=None)
    assert alp is not None and alp_cap == 1000.0 and not fatal


def test_dry_run_sans_reseau():
    alp, bit, alp_cap, bit_cap, fatal = vet_brokers(None, None, dry=True, cli_equity=2500.0)
    assert alp_cap == 2500.0 and not fatal


def test_dd_kill_switch_coupe_sur_breach(monkeypatch, tmp_path):
    import packages.execution.equity_history as eh
    monkeypatch.setattr(eh, "_F", tmp_path / "eq.json")
    eh.record({"alpaca": 100_000.0}, today="2026-01-01")   # pic
    eh.record({"alpaca": 98_000.0}, today="2026-01-02")
    assert dd_kill_switch(80_000.0, None, None) == 0.0     # −20 % ≤ −15 % → coupe


def test_dd_kill_switch_laisse_passer_sain(monkeypatch, tmp_path):
    import packages.execution.equity_history as eh
    monkeypatch.setattr(eh, "_F", tmp_path / "eq.json")
    eh.record({"alpaca": 100_000.0}, today="2026-01-01")
    assert dd_kill_switch(97_000.0, None, None) == 1.0     # −3 % : rien à couper


def test_dd_kill_switch_historique_vide(monkeypatch, tmp_path):
    import packages.execution.equity_history as eh
    monkeypatch.setattr(eh, "_F", tmp_path / "eq.json")
    assert dd_kill_switch(10_000.0, None, None) == 1.0     # 1 point : pas de faux gel


def test_fail_loud_exit_non_zero():
    with pytest.raises(SystemExit) as exc:
        fail_loud(["clé invalide"], None, code=3)
    assert exc.value.code == 3
