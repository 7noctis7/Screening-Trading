"""Garde-fous d'exécution (audit 07/15) : inconnu ≠ zéro, brokers morts écartés,
kill-switch drawdown réel, fail-loud. Brokers factices — aucun réseau."""

import pytest

from packages.execution.live_guards import (
    APERCU_DEFAUT,
    DD_LIMIT_DEFAUT,
    FENETRE_DD_DEFAUT,
    current_values,
    dd_kill_switch,
    fail_loud,
    resolve_dd_window,
    resolve_intraday_dd_limit,
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


def _clear_intraday_dd_env(monkeypatch):
    monkeypatch.delenv("QUANT_INTRADAY_DD", raising=False)
    monkeypatch.delenv("QUANT_DD_WINDOW", raising=False)


def _hist(monkeypatch, tmp_path, points: list[float]):
    """Un point d'equity Alpaca par jour, à partir du 2026-01-01."""
    import packages.execution.equity_history as eh
    monkeypatch.setattr(eh, "_F", tmp_path / "eq.json")
    for i, v in enumerate(points):
        eh.record({"alpaca": v}, today=f"2026-{1 + i // 28:02d}-{1 + i % 28:02d}")


def test_le_seuil_par_defaut_est_15pct_depuis_le_plus_haut(monkeypatch):
    """17/11 : le kill-switch lit `max_drawdown_pct` (15 %), PAS la limite journalière
    `max_daily_drawdown_pct` (5 %) que #425 lui avait branchée par erreur."""
    _clear_intraday_dd_env(monkeypatch)
    assert resolve_intraday_dd_limit() == pytest.approx(-0.15)
    assert DD_LIMIT_DEFAUT == pytest.approx(-0.15)
    assert resolve_dd_window() == FENETRE_DD_DEFAUT == 63


def test_overrides_env_du_seuil_et_de_la_fenetre(monkeypatch):
    _clear_intraday_dd_env(monkeypatch)
    monkeypatch.setenv("QUANT_INTRADAY_DD", "-0.12")
    assert resolve_intraday_dd_limit() == pytest.approx(-0.12)
    monkeypatch.setenv("QUANT_INTRADAY_DD", "")
    assert resolve_intraday_dd_limit() == pytest.approx(-0.15)  # vide → yaml
    monkeypatch.setenv("QUANT_DD_WINDOW", "20")
    assert resolve_dd_window() == 20


@pytest.mark.parametrize("brut", ["abc", "1", "0", "-5"])
def test_une_fenetre_illisible_retombe_sur_le_defaut(monkeypatch, brut):
    """Une faute de frappe ne doit ni désarmer le garde-fou ni le rendre permanent."""
    _clear_intraday_dd_env(monkeypatch)
    monkeypatch.setenv("QUANT_DD_WINDOW", brut)
    assert resolve_dd_window() == 63


def test_yaml_lu_pour_le_seuil_et_la_fenetre(tmp_path):
    from packages.execution.live_guards import _dd_limit_depuis_yaml
    f = tmp_path / "risk.yaml"
    f.write_text("portfolio:\n  max_daily_drawdown_pct: 0.05\n  max_drawdown_pct: 0.2\n"
                 "  drawdown_window_sessions: 30\n")
    assert _dd_limit_depuis_yaml(f) == pytest.approx(-0.2)
    assert resolve_dd_window(f) == 30
    assert _dd_limit_depuis_yaml(tmp_path / "absent.yaml") == pytest.approx(-0.15)


def test_le_cas_du_16_11_ne_bloque_plus(monkeypatch, tmp_path):
    """Le compte du 16/11 : pic 102 397 $, dernier 93 588 $ (−8,6 %). Bloqué à −5 %,
    il ne l'est plus à −15 %."""
    _clear_intraday_dd_env(monkeypatch)
    _hist(monkeypatch, tmp_path, [100_000.0, 102_396.89, 97_000.0])
    assert dd_kill_switch(93_587.87, None, None) == 1.0


def test_dd_kill_switch_coupe_sur_breach(monkeypatch, tmp_path):
    _clear_intraday_dd_env(monkeypatch)
    _hist(monkeypatch, tmp_path, [100_000.0, 98_000.0])
    assert dd_kill_switch(80_000.0, None, None) == 0.0     # −20 % ≤ −15 % → coupe


def test_dd_kill_switch_laisse_passer_sain(monkeypatch, tmp_path):
    _clear_intraday_dd_env(monkeypatch)
    _hist(monkeypatch, tmp_path, [100_000.0])
    assert dd_kill_switch(90_000.0, None, None) == 1.0     # −10 % > −15 % : OK


def test_dd_kill_switch_env_override_durcit(monkeypatch, tmp_path):
    _clear_intraday_dd_env(monkeypatch)
    monkeypatch.setenv("QUANT_INTRADAY_DD", "-0.05")
    _hist(monkeypatch, tmp_path, [100_000.0])
    assert dd_kill_switch(94_000.0, None, None) == 0.0     # −6 % ≤ −5 %


def test_un_plus_haut_sorti_de_la_fenetre_ne_bloque_plus(monkeypatch, tmp_path):
    """Le piège corrigé : un blocage ne peut plus durer plus longtemps que la fenêtre.
    Pic à 100 000 puis 70 séances à 80 000 (−20 %) : bloqué à 63 séances de recul,
    plus rien à couper dès que le pic en est sorti."""
    _clear_intraday_dd_env(monkeypatch)
    _hist(monkeypatch, tmp_path, [100_000.0] + [80_000.0] * 70)
    assert dd_kill_switch(80_000.0, None, None) == 1.0
    monkeypatch.setenv("QUANT_DD_WINDOW", "200")
    assert dd_kill_switch(80_000.0, None, None) == 0.0     # pic encore dans la fenêtre


def test_dd_kill_switch_historique_vide(monkeypatch, tmp_path):
    _clear_intraday_dd_env(monkeypatch)
    import packages.execution.equity_history as eh
    monkeypatch.setattr(eh, "_F", tmp_path / "eq.json")
    assert dd_kill_switch(10_000.0, None, None) == 1.0     # 1 point : pas de faux gel


def test_l_etat_affiche_est_celui_du_run_et_donne_le_niveau_de_reprise(monkeypatch, tmp_path):
    """La page Positions lit `etat_courant` : même règle, même verdict que le robot."""
    from packages.execution.live_guards import etat_courant, etat_kill_switch
    _clear_intraday_dd_env(monkeypatch)
    _hist(monkeypatch, tmp_path, [100_000.0, 84_000.0])
    e = etat_courant()
    assert e["available"] and e["breach"] and e["fenetre"] == 63
    assert e["reprise"] == pytest.approx(85_000.0) and e["depuis"] == "2026-01-02"
    assert dd_kill_switch(84_000.0, None, None) == 0.0
    assert etat_kill_switch([100.0, 90.0], -0.15, 63)["breach"] is False


def test_l_etat_affiche_ne_casse_jamais_la_page(monkeypatch):
    import packages.execution.equity_history as eh
    from packages.execution.live_guards import etat_courant
    monkeypatch.setattr(eh, "_load", lambda: (_ for _ in ()).throw(RuntimeError("KO")))
    assert etat_courant()["available"] is False


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
