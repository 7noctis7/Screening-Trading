"""Une base valide peut être parfaitement périmée. L'audit doit le dire.

L'audit d'origine vérifiait l'intégrité de ce qui est présent, jamais que quelque chose ARRIVE
encore. Collecte morte = base intacte et obsolète, publiée avec le même aplomb.
"""
from dataclasses import dataclass
from datetime import date, timedelta

from packages.data.audit import audit_freshness


@dataclass
class B:
    ts: date
    open: float = 10.0
    high: float = 11.0
    low: float = 9.0
    close: float = 10.0
    volume: float = 1000.0


def _serie(fin: date, n: int = 40, pas: int = 1):
    return [B(fin - timedelta(days=(n - 1 - i) * pas)) for i in range(n)]


AUJ = date(2026, 8, 21)          # un vendredi


def test_base_a_jour_aucune_anomalie():
    data = {"AAPL": _serie(AUJ), "MSFT": _serie(AUJ)}
    assert audit_freshness(data, now=AUJ) == []


def test_collecte_arretee_est_critique():
    vieux = AUJ - timedelta(days=30)
    data = {"AAPL": _serie(vieux), "MSFT": _serie(vieux)}
    a = audit_freshness(data, now=AUJ)
    assert len(a) == 1 and a[0].severity == "critical"
    assert "collecte arrêtée" in a[0].detail


def test_week_end_ne_declenche_rien():
    """Vendredi soir, la dernière barre est celle de jeudi ou vendredi : c'est normal."""
    data = {"AAPL": _serie(AUJ - timedelta(days=1))}
    assert audit_freshness(data, now=AUJ) == []


def test_serie_isolee_en_retard_est_majeure_pas_critique():
    """Un titre délisté ne doit pas faire passer toute la base pour morte."""
    data = {"AAPL": _serie(AUJ), "MSFT": _serie(AUJ),
            "VIEUX": _serie(AUJ - timedelta(days=45))}
    a = audit_freshness(data, now=AUJ)
    assert [x.symbol for x in a] == ["VIEUX"]
    assert a[0].severity == "major"
    assert "délistée" in a[0].detail


def test_crypto_jugee_sur_le_calendrier_pas_les_jours_ouvres():
    """La crypto cote 7 j/7 : trois jours sans barre est anormal, contrairement à une action."""
    data = {"AAPL": _serie(AUJ), "MSFT": _serie(AUJ),
            "BTC-USD": _serie(AUJ - timedelta(days=5))}
    a = audit_freshness(data, now=AUJ)
    assert [x.symbol for x in a] == ["BTC-USD"]


def test_jeu_vide_ou_sans_dates_est_critique():
    a = audit_freshness({}, now=AUJ)
    assert len(a) == 1 and a[0].severity == "critical"


def test_la_fraicheur_ne_pollue_pas_l_audit_d_integrite():
    """`audit_dataset` audite une TRANCHE : s'arrêter dans le passé y est sain.

    Seul `audit_and_report` — le point d'entrée du pipeline — pose la question du jour.
    """
    from packages.data.audit import audit_and_report, audit_dataset
    vieux = {"AAA": _serie(AUJ - timedelta(days=30))}
    assert not audit_dataset(vieux, now=AUJ).critical
    assert audit_and_report(vieux, universe=["AAA"], now=AUJ).critical
