"""Le garde-fou « déjà rebalancé aujourd'hui » — dérivé du doublon RÉEL du 15/09.

Le cas de référence n'est pas inventé : c'est le relevé Alpaca de ce jour-là, où sept
lignes ouvertes à 18:32 UTC ont été soldées à la quantité près à 19:04 UTC.
"""

from datetime import date

import pytest

from packages.execution.garde_journaliere import (
    NOTIONNEL_MINIMUM,
    ORDRES_MINIMUM,
    _jour,
    evaluer,
    message,
    ordres_du_jour,
)

J = date(2026, 9, 15)


def _o(iso: str, sym: str = "VEEV", notional: float = 2000.0, qty: float = 7.4) -> dict:
    return {"date": iso, "symbol": sym, "notional": notional, "qty": qty}


# ─── Le cas réel ───────────────────────────────────────────────────────────────────────

def test_le_second_passage_du_15_09_aurait_ete_refuse():
    """Les treize achats de 18:32 suffisent à refuser le passage de 19:04."""
    achats = [_o("2026-09-15T18:32:44+00:00", s, n) for s, n in
              [("QQQ", 7262), ("SWKS", 2945), ("SNOW", 2945), ("TEN", 2816),
               ("OSCR", 2815), ("T", 2775), ("TYL", 2246), ("VEEV", 2007),
               ("PLTR", 1847), ("ASST", 1737)]]
    d = evaluer(achats, J)
    assert d["deja_rebalance"] is True
    assert d["n_ordres"] == 10
    assert d["notionnel"] == pytest.approx(29395.0)


# ─── Ce qui NE doit PAS déclencher ─────────────────────────────────────────────────────

def test_historique_vide_laisse_passer():
    """Vide peut vouloir dire « illisible ». Le doute profite au trading : un garde-fou
    qui bloque sur une lecture ratée gèlerait le robot une journée sans motif."""
    assert evaluer([], J)["deja_rebalance"] is False


def test_les_fills_de_la_veille_ne_comptent_pas():
    veille = [_o("2026-09-14T19:04:13+00:00", "PLTR"), _o("2026-09-14T19:04:14+00:00", "SNOW")]
    assert evaluer(veille, J)["deja_rebalance"] is False


def test_un_seul_ordre_ne_fait_pas_une_journee():
    """Un ordre isolé ressemble à une intervention manuelle, pas à un passage du robot."""
    d = evaluer([_o("2026-09-15T18:32:44+00:00", "VEEV", 50_000.0)], J)
    assert d["n_ordres"] == 1 and d["deja_rebalance"] is False


def test_des_poussieres_ne_font_pas_une_journee():
    """Résidus d'arrondi : plusieurs ordres, mais un notionnel négligeable."""
    poussiere = [_o("2026-09-15T18:32:44+00:00", "VEEV", 3.0),
                 _o("2026-09-15T18:32:45+00:00", "TYL", 4.0),
                 _o("2026-09-15T18:32:46+00:00", "SNOW", 2.0)]
    assert sum(o["notional"] for o in poussiere) < NOTIONNEL_MINIMUM
    assert evaluer(poussiere, J)["deja_rebalance"] is False


def test_les_deux_seuils_sont_conjoints():
    """Le compte d'ordres ET le notionnel doivent être atteints — l'un sans l'autre
    laisse passer, sinon un seul gros ordre manuel bloquerait la journée."""
    juste = [_o("2026-09-15T12:00:00+00:00", "A", NOTIONNEL_MINIMUM)
             for _ in range(ORDRES_MINIMUM)]
    assert evaluer(juste, J)["deja_rebalance"] is True


def test_quantite_nulle_ignoree():
    """Un ordre annulé/non rempli ne prouve rien."""
    annules = [dict(_o("2026-09-15T18:32:44+00:00", "VEEV"), qty=0.0),
               dict(_o("2026-09-15T18:32:45+00:00", "TYL"), qty=0.0)]
    assert evaluer(annules, J)["deja_rebalance"] is False


# ─── Horodatages ───────────────────────────────────────────────────────────────────────

def test_horodatage_illisible_ne_compte_jamais_pour_aujourdhui():
    """Une chaîne qu'on n'a pas comprise ne doit pas bloquer la journée sur sa foi."""
    assert _jour("pas une date") is None
    assert _jour("") is None
    assert evaluer([_o("n'importe quoi", "A"), _o("", "B")], J)["deja_rebalance"] is False


def test_horodatage_naif_lu_en_utc():
    assert _jour("2026-09-15T18:32:44") == J


def test_suffixe_z_accepte():
    assert _jour("2026-09-15T18:32:44Z") == J


def test_fuseau_decale_ramene_a_la_journee_utc():
    """21:04 à Paris (UTC+2), c'est 19:04 UTC — le MÊME jour, pas le lendemain."""
    assert _jour("2026-09-15T21:04:13+02:00") == J
    # …et 01:30 à Paris appartient à la journée UTC PRÉCÉDENTE.
    assert _jour("2026-09-16T01:30:00+02:00") == date(2026, 9, 15)


def test_ordres_du_jour_filtre_sur_la_date():
    tous = [_o("2026-09-14T19:00:00+00:00", "A"), _o("2026-09-15T19:00:00+00:00", "B")]
    assert [o["symbol"] for o in ordres_du_jour(tous, J)] == ["B"]


# ─── Désarmement explicite ─────────────────────────────────────────────────────────────

def test_quant_rebal_multi_desarme(monkeypatch):
    achats = [_o("2026-09-15T18:32:44+00:00", "VEEV"), _o("2026-09-15T18:32:45+00:00", "TYL")]
    monkeypatch.setenv("QUANT_REBAL_MULTI", "1")
    d = evaluer(achats, J)
    assert d["deja_rebalance"] is False and d["desarme"] is True
    # Les faits restent VRAIS même désarmé : c'est la décision qui change, pas la mesure.
    assert d["n_ordres"] == 2


def test_valeur_autre_que_1_narme_pas_le_desarmement(monkeypatch):
    monkeypatch.setenv("QUANT_REBAL_MULTI", "oui")
    achats = [_o("2026-09-15T18:32:44+00:00", "VEEV"), _o("2026-09-15T18:32:45+00:00", "TYL")]
    assert evaluer(achats, J)["deja_rebalance"] is True


# ─── Le message ────────────────────────────────────────────────────────────────────────

def test_le_refus_dit_ce_qui_a_deja_ete_fait():
    """Un refus qui ne nomme rien ressemble à une panne — et on le contourne."""
    d = evaluer([_o("2026-09-15T18:32:44+00:00", "VEEV"),
                 _o("2026-09-15T18:32:45+00:00", "TYL")], J)
    m = message(d)
    assert "VEEV" in m and "TYL" in m and "2026-09-15" in m
    assert "--forcer" in m                      # la sortie de secours est écrite
    assert "crontab -l" in m                    # et la piste à suivre aussi


def test_le_separateur_de_milliers_ne_mange_pas_la_liste_de_symboles():
    """L'espace fine se pose sur le NOMBRE, pas sur la phrase : sinon « TYL, VEEV »
    devenait « TYL  VEEV » et la liste perdait sa ponctuation."""
    d = evaluer([_o("2026-09-15T18:32:44+00:00", "VEEV", 12_000.0),
                 _o("2026-09-15T18:32:45+00:00", "TYL", 12_000.0)], J)
    m = message(d)
    assert "TYL, VEEV" in m
    assert "24 000 $" in m
