"""Garde-fous d'exécution (audit 07/15) : inconnu ≠ zéro, brokers morts écartés,
kill-switch drawdown réel, fail-loud. Brokers factices — aucun réseau."""

import pytest

from packages.execution.live_guards import (
    APERCU_DEFAUT,
    current_values,
    dd_kill_switch,
    fail_loud,
    simule,
    vet_brokers,
)


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
    alp, bit, alp_cap, bit_cap, fatal = vet_brokers(
        _Dead(), None, dry=False, cli_equity=None)
    assert alp is None and alp_cap == 0.0 and fatal   # écarté + motif d'échec (run rouge)


def test_broker_sain_conserve():
    alp, bit, alp_cap, bit_cap, fatal = vet_brokers(
        _Ok(), None, dry=False, cli_equity=None)
    assert alp is not None and alp_cap == 1000.0 and not fatal


def test_dry_run_sans_reseau():
    alp, bit, alp_cap, bit_cap, fatal = vet_brokers(
        None, None, dry=True, cli_equity=2500.0)
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


# APERÇU vs SIMULATION (05/09). `make live` affichait « détenu 0 $ » sur un compte plein
# et un capital de 10 000 $ : chaque cible sortait au dixième de sa taille réelle, et
# l'aperçu annonçait l'achat de tout le portefeuille par-dessus l'existant — le mode de
# défaillance que le principe 1 de ce module interdit au run LIVE, reproduit à l'écran.


def test_equity_impose_veut_dire_simulation():
    """`--equity` = « portefeuille neuf » : le détenu est ignoré à dessein."""
    assert simule(dry=True, cli_equity=2500.0) is True
    alp, bit, alp_cap, bit_cap, fatal = vet_brokers(
        _Ok(), None, dry=True, cli_equity=2500.0)
    assert alp_cap == 2500.0 and not fatal             # equity du broker JAMAIS lue


def test_apercu_sans_equity_lit_le_compte_reel():
    """Sans `--equity`, l'aperçu doit décrire le compte : sinon il n'annonce rien."""
    assert simule(dry=True, cli_equity=None) is False
    alp, bit, alp_cap, bit_cap, fatal = vet_brokers(
        _Ok(), None, dry=True, cli_equity=None)
    assert alp_cap == 1000.0 and alp is not None and not fatal


def test_apercu_sans_broker_se_replie_au_lieu_de_tout_mettre_a_zero():
    """05/09 : capital 0 → cibles 0 → un tableau de lignes vides, muet sur la cause."""
    alp, bit, alp_cap, bit_cap, fatal = vet_brokers(
        None, None, dry=True, cli_equity=None)
    assert alp_cap == APERCU_DEFAUT and fatal == []


def test_apercu_equity_illisible_se_replie_sans_etre_fatal():
    """Un aperçu n'envoie aucun ordre : le sanctionner comme un live n'a pas de sens."""
    alp, bit, alp_cap, bit_cap, fatal = vet_brokers(
        _Dead(), None, dry=True, cli_equity=None)
    assert alp_cap == APERCU_DEFAUT and alp is not None and fatal == []


def test_live_ignore_equity_de_la_ligne_de_commande():
    """En live, `--equity` ne doit jamais se substituer à l'equity du courtier."""
    assert simule(dry=False, cli_equity=2500.0) is False
    alp, bit, alp_cap, bit_cap, fatal = vet_brokers(
        _Ok(), None, dry=False, cli_equity=2500.0)
    assert alp_cap == 1000.0
