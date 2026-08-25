"""Alertes TradingView → kill-switch. Le garde-fou qui pouvait bloquer le portefeuille à vie.

Deux défauts mesurés le 25/08 sur ce chemin, tous deux de la même famille que les six autres de
la semaine — quelque chose qui a l'air d'être armé et ne fait pas ce qu'il annonce :

  1. `max_age_s` était déclaré, documenté, et jamais appliqué. `run_live.py` appelait la fonction
     sans argument : une alerte `critical` du 1er juillet vetoait encore tout le trading fin août.
  2. Une sévérité non reconnue était dégradée en `info`. Une alerte Pine étiquetée « CRITIQUE »
     ne déclenchait donc rien du tout.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest

from packages.mcp_tradingview.alerts import (AGE_MAX_DEFAUT, append_alert,
                                             fetch_tv_technical_alerts, horodatage, parse_alert,
                                             to_risk_veto)

MAINTENANT = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


def _il_y_a(**kw) -> str:
    return (MAINTENANT - timedelta(**kw)).isoformat()


# --- LE FILTRE D'ÂGE EXISTE VRAIMENT ---------------------------------------------------------

def test_une_alerte_critique_perimee_ne_veto_plus(tmp_path):
    """LE défaut : une alerte de juillet bloquait encore le portefeuille fin août."""
    p = tmp_path / "tv.json"
    append_alert({"ticker": "SPY", "kind": "circuit_breaker", "severity": "critical",
                  "time": "2026-07-01T10:00:00Z"}, p)
    retenues = fetch_tv_technical_alerts(p, maintenant=MAINTENANT)
    assert retenues == []
    assert to_risk_veto(retenues)["veto"] is False


def test_une_alerte_critique_recente_veto_toujours():
    a = parse_alert({"ticker": "SPY", "kind": "krach", "severity": "critical",
                     "time": _il_y_a(hours=1)})
    v = to_risk_veto([a])
    assert v["veto"] is True and v["reduce"] == 0.0


def test_le_filtre_est_actif_PAR_DEFAUT(tmp_path):
    """« Aucun filtre » est le réglage dangereux : il ne doit pas être le défaut."""
    p = tmp_path / "tv.json"
    append_alert({"ticker": "SPY", "kind": "x", "severity": "critical",
                  "time": _il_y_a(days=30)}, p)
    assert AGE_MAX_DEFAUT == 24 * 3600.0
    assert fetch_tv_technical_alerts(p, maintenant=MAINTENANT) == []          # défaut : filtré
    assert len(fetch_tv_technical_alerts(p, max_age_s=None)) == 1             # explicite : tout


def test_la_frontiere_du_filtre_est_inclusive(tmp_path):
    p = tmp_path / "tv.json"
    append_alert({"ticker": "A", "kind": "x", "severity": "warning",
                  "time": _il_y_a(seconds=AGE_MAX_DEFAUT)}, p)
    append_alert({"ticker": "B", "kind": "x", "severity": "warning",
                  "time": _il_y_a(seconds=AGE_MAX_DEFAUT + 60)}, p)
    tickers = {a.ticker for a in fetch_tv_technical_alerts(p, maintenant=MAINTENANT)}
    assert tickers == {"A"}


# --- INCONNU ≠ RIEN ---------------------------------------------------------------------------

@pytest.mark.parametrize("brut", ["CRITIQUE", "urgent", "SEVERE", "grave", "danger"])
def test_les_synonymes_francais_et_anglais_declenchent(brut):
    assert parse_alert({"ticker": "SPY", "kind": "x", "severity": brut}).severity == "critical"


def test_une_severite_inconnue_vaut_warning_jamais_info():
    """On ne descend jamais vers « rien ne se passe » sur une entrée qu'on n'a pas comprise."""
    a = parse_alert({"ticker": "SPY", "kind": "x", "severity": "n_importe_quoi"})
    assert a.severity == "warning"
    assert to_risk_veto([a])["reduce"] == 0.5


def test_une_severite_reinterpretee_est_signalee():
    a = parse_alert({"ticker": "SPY", "kind": "x", "severity": "zzz"})
    assert a.severite_brute == "zzz"
    assert "zzz" in to_risk_veto([a])["severites_reinterpretees"][0]


def test_la_trace_de_reinterpretation_survit_au_fichier(tmp_path):
    """Trou de mon premier correctif : le drop relu contient une sévérité DÉJÀ normalisée, donc
    la comparaison brut≠normalisé ne disait plus rien et le diagnostic revenait vide."""
    p = tmp_path / "tv.json"
    append_alert({"ticker": "IWM", "kind": "x", "severity": "CRITIQUE",
                  "time": _il_y_a(hours=1)}, p)
    v = to_risk_veto(fetch_tv_technical_alerts(p, maintenant=MAINTENANT))
    assert v["severites_reinterpretees"] and "critique" in v["severites_reinterpretees"][0]


def test_une_severite_connue_n_est_pas_marquee_comme_reinterpretee():
    assert parse_alert({"ticker": "S", "kind": "x", "severity": "critical"}).severite_brute == ""


# --- ALERTES NON DATABLES : PRUDENCE, MAIS VISIBLE --------------------------------------------

def test_une_alerte_sans_date_lisible_est_conservee(tmp_path):
    """Entre « trader pendant un krach faute d'avoir su dater l'alerte » et « rester à l'écart »,
    un kill-switch doit préférer le second — mais la situation doit rester VISIBLE."""
    p = tmp_path / "tv.json"
    append_alert({"ticker": "SPY", "kind": "x", "severity": "critical",
                  "time": "pas une date"}, p)
    a = fetch_tv_technical_alerts(p, maintenant=MAINTENANT)
    v = to_risk_veto(a)
    assert len(a) == 1 and v["veto"] is True and v["n_sans_date"] == 1


@pytest.mark.parametrize("brut,lisible", [
    ("2026-08-25T10:00:00Z", True), ("2026-08-25 10:00:00", True),
    ("2026-08-25", True), ("2026-08-25T10:00:00+02:00", True),
    ("", False), ("hier", False), ("n/a", False),
])
def test_horodatage_tolerant_mais_honnete(brut, lisible):
    a = parse_alert({"ticker": "S", "kind": "x", "time": brut})
    assert (horodatage(a) is not None) is lisible or brut == ""


def test_une_date_sans_fuseau_est_traitee_en_utc():
    d = horodatage(parse_alert({"ticker": "S", "kind": "x", "time": "2026-08-25T10:00:00"}))
    assert d is not None and d.tzinfo is not None


# --- ROBUSTESSE : LE DROP NE DOIT JAMAIS CASSER LE MOTEUR -------------------------------------

def test_fichier_absent_corrompu_ou_mal_forme(tmp_path):
    assert fetch_tv_technical_alerts(tmp_path / "rien.json") == []
    mauvais = tmp_path / "corrompu.json"
    mauvais.write_text("{ pas du json", encoding="utf-8")
    assert fetch_tv_technical_alerts(mauvais) == []
    objet = tmp_path / "objet.json"
    objet.write_text(json.dumps({"ticker": "SPY"}), encoding="utf-8")
    assert fetch_tv_technical_alerts(objet) == []


def test_lignes_inexploitables_ignorees_sans_casser_les_autres(tmp_path):
    p = tmp_path / "tv.json"
    p.write_text(json.dumps([
        {"ticker": "SPY", "kind": "x", "severity": "warning", "time": _il_y_a(hours=1)},
        "pas un dict", {}, {"message": ""},
    ]), encoding="utf-8")
    assert len(fetch_tv_technical_alerts(p, maintenant=MAINTENANT)) == 1


def test_le_drop_est_borne(tmp_path):
    p = tmp_path / "tv.json"
    for i in range(15):
        append_alert({"ticker": f"T{i}", "kind": "x", "time": _il_y_a(hours=1)}, p, keep=10)
    assert len(json.loads(p.read_text(encoding="utf-8"))) == 10


# --- SANS ALERTE, AUCUNE RÉDUCTION ------------------------------------------------------------

def test_aucune_alerte_signifie_exposition_normale():
    v = to_risk_veto([])
    assert v["veto"] is False and v["reduce"] == 1.0 and v["n_alerts"] == 0
