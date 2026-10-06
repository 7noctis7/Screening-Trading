"""Un seul compteur d'essais, et aucun « promu » dont le DSR est sous le gate.

Jusqu'au 06/10 : `trial_count` comptait des lignes (41), `deflation_params` des essais
(5 738), et la porte de déploiement déflatait avec le premier. Trois facteurs restaient
« promu » avec un DSR de 0,0 à 0,01.
"""

from packages.research.gate import DSR_MIN
from packages.research.ledger import (
    append_record,
    compter_essais,
    deflation_params,
    read_records,
    trial_count,
)


def test_les_deux_lectures_donnent_le_meme_n_sur_le_registre_reel():
    assert trial_count() == deflation_params()[0] == compter_essais(read_records())


def test_relance_identique_ne_compte_pas_un_autre_label_si(tmp_path):
    p = tmp_path / "h.jsonl"
    for _ in range(3):
        append_record({"facteur": "ic", "horizon": 20, "params": {"saut": 0}}, p)
    assert trial_count(p) == 1
    append_record({"facteur": "ic", "horizon": 60, "params": {"saut": 0}}, p)
    append_record({"facteur": "ic", "horizon": 20, "params": {"saut": 21}}, p)
    assert trial_count(p) == 3 == deflation_params(p)[0]


def test_un_balayage_compte_pour_ses_scenarios(tmp_path):
    p = tmp_path / "h.jsonl"
    append_record({"facteur": "grille", "n_essais": 480}, p)
    append_record({"facteur": "grille", "n_essais": 480}, p)        # relance
    append_record({"facteur": "autre"}, p)
    assert trial_count(p) == 481 == deflation_params(p)[0]


def _dernier_mot(recs):
    dernier = {}
    for r in recs:
        f = r.get("facteur")
        if not f:
            continue
        if f not in dernier or str(r.get("date", "")) >= str(dernier[f].get("date", "")):
            dernier[f] = r
    return list(dernier.values())


def test_aucun_promu_courant_sous_le_seuil_dsr():
    fautifs = [r["facteur"] for r in _dernier_mot(read_records())
               if r.get("statut") == "promu"
               and isinstance(r.get("dsr"), (int, float)) and r["dsr"] <= DSR_MIN]
    assert not fautifs, f"« promu » avec un DSR ≤ {DSR_MIN} : {fautifs}"
