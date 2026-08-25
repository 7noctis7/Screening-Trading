

# --- SÉRIES AJOUTÉES LE 25/08 ----------------------------------------------------------------

def test_aucun_identifiant_en_double():
    """Deux entrées pour le même identifiant produiraient deux appels et deux lignes identiques."""
    from packages.macro.fred import SERIES

    ids = [s[0] for s in SERIES]
    assert len(ids) == len(set(ids)), f"doublons : {[i for i in ids if ids.count(i) > 1]}"


def test_chaque_justification_correspond_a_une_serie_reelle():
    """Une justification orpheline signale une série retirée dont on a oublié la trace."""
    from packages.macro.fred import POURQUOI, SERIES

    ids = {s[0] for s in SERIES}
    assert set(POURQUOI) <= ids, f"orphelines : {set(POURQUOI) - ids}"


def test_les_series_ajoutees_sont_justifiees():
    """Le critère d'ajout n'est pas « c'est de la macro » mais « par quel canal ceci déplace-t-il
    une exposition ? ». Une série sans réponse écrite est une série à retirer."""
    from packages.macro.fred import POURQUOI

    ajoutees = {"ICSA", "SAHMREALTIME", "T5YIFR", "NFCI", "BAMLC0A0CM", "WALCL", "DTWEXBGS"}
    assert ajoutees <= set(POURQUOI)
    assert all(len(POURQUOI[s]) > 40 for s in ajoutees)   # une justification, pas une étiquette


def test_le_spread_IG_accompagne_le_haut_rendement():
    """C'est leur ÉCART qui distingue un stress de crédit généralisé d'une aversion cantonnée
    aux émetteurs fragiles — l'un sans l'autre ne dit pas grand-chose."""
    from packages.macro.fred import SERIES

    ids = {s[0] for s in SERIES}
    assert {"BAMLH0A0HYM2", "BAMLC0A0CM"} <= ids


def test_le_pourquoi_est_publie_dans_le_snapshot(monkeypatch):
    """La justification doit voyager avec la donnée, pas rester dans le code."""
    import packages.macro.fred as F

    monkeypatch.setenv("FRED_API_KEY", "factice")
    monkeypatch.setattr(F, "_fetch", lambda sid, units, key: {
        "value": 1.0, "date": "2026-08-01", "delta": 0.0, "retard_jours": 1, "perimee": False})
    snap = F.macro_snapshot()
    assert snap["available"] and snap["pourquoi"]["NFCI"]


# --- DÉTECTION DE PÉREMPTION : NE PAS CRIER AU LOUP -------------------------------------------

def _dates_depuis(fin, espacements):
    from datetime import date, timedelta
    d = date.fromisoformat(fin)
    out = [d.isoformat()]
    for e in espacements:
        d = d - timedelta(days=e)
        out.append(d.isoformat())
    return out


def test_une_serie_quotidienne_survit_a_un_week_end(monkeypatch):
    """LE faux positif du 25/08 : DGS2, DGS10 et DTWEXBGS signalées « périmées » à 4 jours de
    retard un mardi — c'est-à-dire un vendredi plus un week-end. La cadence était estimée par le
    plus PETIT espacement (1 jour pour une série quotidienne), donc 3 jours suffisaient à
    dépasser le seuil. Un détecteur qui se trompe 4 fois sur 5 apprend à être ignoré."""
    from datetime import date

    import packages.macro.fred as F

    class Mardi(date):
        @classmethod
        def today(cls):
            return date(2026, 8, 25)

    monkeypatch.setattr(F, "date", Mardi)
    quotidienne = _dates_depuis("2026-08-21", [1, 1, 1, 3, 1, 1, 1, 3, 1, 1, 1])
    retard, perimee = F._retard(quotidienne)
    assert retard == 4 and perimee is False


def test_une_serie_reellement_arretee_est_signalee(monkeypatch):
    """`LRHUTTTTEZM156S` : dernière observation 2023-01-01, 1332 jours. Arrêtée, pas en retard."""
    from datetime import date

    import packages.macro.fred as F

    class Aujourdhui(date):
        @classmethod
        def today(cls):
            return date(2026, 8, 25)

    monkeypatch.setattr(F, "date", Aujourdhui)
    morte = _dates_depuis("2023-01-01", [30] * 11)
    retard, perimee = F._retard(morte)
    assert retard > 1300 and perimee is True


def test_une_interruption_exceptionnelle_ne_relache_pas_le_seuil_pour_toujours(monkeypatch):
    """Le MAXIMUM des espacements serait trop indulgent : un arrêt technique de 90 jours dans
    l'historique relèverait le seuil définitivement. Un quantile haut absorbe les week-ends et
    les jours fériés, pas un arrêt."""
    from datetime import date

    import packages.macro.fred as F

    class Aujourdhui(date):
        @classmethod
        def today(cls):
            return date(2026, 8, 25)

    monkeypatch.setattr(F, "date", Aujourdhui)
    avec_trou = _dates_depuis("2026-05-01", [1, 1, 90, 1, 1, 1, 3, 1, 1, 1, 1])
    _retard_j, perimee = F._retard(avec_trou)
    assert perimee is True, "116 jours de retard ne doivent pas être excusés par un vieux trou"


def test_la_serie_euro_morte_a_ete_retiree():
    """Constatée morte le 25/08 (1332 j). Aucun remplaçant n'est deviné : remplacer une série
    morte par une série peut-être morte n'améliore rien."""
    from packages.macro.fred import SERIES

    assert "LRHUTTTTEZM156S" not in {s[0] for s in SERIES}


def test_dates_vides_ou_illisibles_ne_levent_pas():
    from packages.macro.fred import _retard

    assert _retard([]) == (0, False)
    assert _retard(["pas une date"]) == (0, False)
    assert _retard(["2026-08-21"])[1] is False        # une seule obs : aucune cadence mesurable
