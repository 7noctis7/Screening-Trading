

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
