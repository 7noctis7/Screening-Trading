"""Courbes de benchmark du dashboard : appariées PAR DATE, pas par position.

Sixième occurrence de l'empilement positionnel (04/09). `bench_series` collait le
i-ème cours du S&P sur la i-ème date du portefeuille. Les deux calendriers diffèrent
(indices vs univers négociable) : la courbe tracée sous le portefeuille était décalée.
"""
from packages.reporting.bench_curves import bench_series


def _jours(n: int, depart=(2024, 1, 1)) -> list[str]:
    from datetime import date, timedelta
    out, d = [], date(*depart)
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def test_valeur_posee_sur_sa_propre_date():
    dates = _jours(6)
    # l'indice ne cote pas la 3e séance : sa 3e valeur appartient à la 4e date
    idx_dates = [d for i, d in enumerate(dates) if i != 2]
    px = [100.0, 101.0, 103.0, 104.0, 105.0]
    serie = bench_series({"S&P 500": (px, idx_dates)}, dates, 10_000.0)["S&P 500"]
    par_date = {p["t"]: p["v"] for p in serie}
    assert par_date[dates[3]] == 10_000.0 * 103.0 / 100.0
    # séance manquante : report du dernier cours CONNU, jamais du suivant
    assert par_date[dates[2]] == par_date[dates[1]] == 10_000.0 * 101.0 / 100.0


def test_position_decalait_la_courbe():
    """Même donnée : l'ancien alignement place 103 sur la 3e date au lieu de la 4e."""
    dates = _jours(6)
    idx_dates = [d for i, d in enumerate(dates) if i != 2]
    px = [100.0, 101.0, 103.0, 104.0, 105.0]
    date_ = bench_series({"X": (px, idx_dates)}, dates, 100.0)["X"]
    par_date = {p["t"]: p["v"] for p in date_}
    par_pos = {p["t"]: p["v"] for p in bench_series({"X": px}, dates, 100.0)["X"]}
    assert par_pos != par_date
    # aligné par la FIN : la plus ancienne séance du portefeuille perd son point…
    assert dates[0] not in par_pos and dates[0] in par_date
    # …et tout ce qui précède le trou est décalé d'une séance
    assert par_pos[dates[1]] == 100.0 and par_date[dates[1]] == 101.0


def test_repli_positionnel_conserve_pour_une_serie_sans_calendrier():
    """Une série synthétique n'a pas de calendrier propre : comportement inchangé."""
    dates = _jours(5)
    serie = bench_series({"S": [10.0, 11.0, 12.0, 13.0, 14.0]}, dates, 1_000.0)["S"]
    assert [p["t"] for p in serie] == dates
    assert serie[0]["v"] == 1_000.0 and serie[-1]["v"] == 1_400.0


def test_nan_jamais_servi_au_front():
    dates = _jours(5)
    px = [100.0, float("nan"), 102.0, None, 104.0]
    for benches in ({"A": (px, dates)}, {"A": px}):
        for p in bench_series(benches, dates, 100.0)["A"]:
            assert p["v"] == p["v"] and p["v"] is not None


def test_aucune_date_commune_ne_produit_pas_de_courbe():
    ailleurs = ([1.0, 2.0, 3.0], _jours(3, (1999, 1, 4)))
    serie = bench_series({"A": ailleurs}, _jours(3), 100.0)
    assert "A" not in serie
