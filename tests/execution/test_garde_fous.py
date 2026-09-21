"""Le témoin des garde-fous compte-t-il ce qui s'est VRAIMENT passé ?

Ces tests ne vérifient pas qu'un champ existe — un champ présent et faux est pire qu'un
champ absent. Ils PROVOQUENT chaque situation et exigent le bon nombre : une réduction
de 4 000 $ doit compter 4 000 $, un refus doit compter le montant entier, une absence
doit rester une absence.
"""

import json

import pytest

from packages.execution import garde_fous as gf
from packages.execution import garde_fous_store as store
from packages.risk.order_gate import EtatCompte, Limites, evaluer


@pytest.fixture
def _store_isole(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "_F", tmp_path / "garde_fous.json")
    return store


def _limites(**kw):
    return Limites(**{"max_poids_ligne": 1.0, "max_poids_ligne_panier": 1.0,
                      "max_positions": 100, "max_ordre_pct": 1.0,
                      "max_exposition": 1.0, **kw})


def test_un_ordre_dans_les_limites_compte_une_observation_et_zero_declenchement():
    c = gf.Collecteur()
    v = evaluer("acheter", 1_000.0, EtatCompte(100_000.0, 0.0, 0), _limites())
    c.portail(v, 1_000.0)
    r = c.rapport()[gf.PORTAIL]
    assert r["observations"] == 1 and r["declenchements"] == 0
    assert r["taux"] == 0.0
    # Mesuré et nul, PAS « non mesurable » : le portail a bien regardé cet ordre.
    assert r["effet_usd"] == 0.0


def test_une_reduction_compte_le_montant_RETENU_pas_le_montant_demande():
    """SABOTAGE. Un témoin qui enregistrerait le montant DEMANDÉ gonflerait l'effet du
    portail d'un facteur dix et ferait croire à une protection qui n'a pas eu lieu."""
    c = gf.Collecteur()
    v = evaluer("acheter", 50_000.0, EtatCompte(100_000.0, 0.0, 0),
                _limites(max_ordre_pct=0.15))
    assert v.autorise and v.reduit and v.montant == pytest.approx(15_000.0)
    c.portail(v, 50_000.0)
    r = c.rapport()[gf.PORTAIL]
    assert r["declenchements"] == 1
    assert r["effet_usd"] == pytest.approx(35_000.0)       # 50 000 demandés − 15 000 retenus
    assert r["effet_moyen"] == pytest.approx(35_000.0)
    assert r["motifs"] == {"taille_ordre": 1}


def test_un_refus_retient_TOUT_le_montant():
    c = gf.Collecteur()
    v = evaluer("acheter", 7_500.0, EtatCompte(100_000.0, 0.0, 40),
                _limites(max_positions=40))
    assert not v.autorise and v.regle == "max_positions"
    c.portail(v, 7_500.0)
    r = c.rapport()[gf.PORTAIL]
    assert r["declenchements"] == 1 and r["effet_usd"] == pytest.approx(7_500.0)


def test_un_desengagement_traverse_sans_compter_de_declenchement():
    """Le portail ne bloque jamais une sortie : le témoin ne doit pas en faire un veto."""
    c = gf.Collecteur()
    v = evaluer("solder", 9_000.0, EtatCompte(0.0, 0.0, 0), _limites(max_ordre_pct=0.01))
    c.portail(v, 9_000.0)
    r = c.rapport()[gf.PORTAIL]
    assert r["declenchements"] == 0 and r["effet_usd"] == 0.0


def test_un_garde_fou_jamais_observe_reste_ABSENT_et_pas_a_zero():
    """ABSENT ≠ ZÉRO. Un garde-fou désarmé et un garde-fou qui n'a rien eu à faire ne
    doivent pas produire la même ligne."""
    c = gf.Collecteur()
    c.observer(gf.KILL_TV)
    r = c.rapport()
    assert gf.KILL_TV in r
    assert gf.DISJONCTEUR not in r                    # jamais observé → il n'existe pas au rapport
    assert r[gf.KILL_TV]["effet_usd"] is None         # non mesurable en dollars ≠ 0,00 $


def test_ERROR_est_collant():
    """Une panne dans le run doit rester visible même si la suite se passe bien."""
    c = gf.Collecteur()
    c.observer(gf.KILL_DD, etat=gf.ERREUR, motif="check_indisponible")
    c.observer(gf.KILL_DD, etat=gf.ACTIVE)
    assert c.rapport()[gf.KILL_DD]["etat"] == gf.ERREUR


class _TemoinCasse:
    def observer(self, *a, **k):
        raise RuntimeError("disque plein")

    def portail(self, *a, **k):
        raise RuntimeError("disque plein")


def test_un_temoin_casse_ne_coute_jamais_un_ordre_et_ne_se_tait_pas(capsys):
    gf.noter(_TemoinCasse(), gf.KILL_DD, etat=gf.ACTIVE)
    gf.noter_portail(_TemoinCasse(), object(), 100.0)
    sortie = capsys.readouterr().out
    assert "indisponible" in sortie                    # l'incident est DIT
    assert sortie.count("indisponible") == 2


def test_aucun_temoin_est_un_cas_normal():
    gf.noter(None, gf.KILL_DD, etat=gf.ACTIVE)
    gf.noter_portail(None, object(), 1.0)              # ne lève pas


def _run(mode, **gardes):
    return {"horodatage": "2026-09-20T10:00:00+00:00", "mode": mode, "gardes": gardes}


def test_agreger_ne_melange_pas_les_apercus_et_le_reel():
    """Un dry-run évalue le portail sans rien envoyer : l'additionner au réel
    répondrait à « qu'aurait fait le robot », pas à « qu'a-t-il fait »."""
    c = gf.Collecteur()
    c.observer(gf.PORTAIL, declenche=True, effet_usd=100.0, motif="poids_ligne")
    runs = [_run("live", **c.rapport()), _run("dry", **c.rapport())]
    assert gf.agreger(runs)["gardes"][gf.PORTAIL]["effet_usd"] == 100.0
    assert gf.agreger(runs, None)["gardes"][gf.PORTAIL]["effet_usd"] == 200.0
    assert gf.agreger(runs)["n_runs"] == 1 and gf.agreger(runs)["n_runs_total"] == 2


def test_verdicts_alerte_sur_un_garde_fou_actif_qui_ne_mord_jamais():
    c = gf.Collecteur()
    for _ in range(5):
        c.observer(gf.KILL_TV, etat=gf.ACTIVE)
    lignes = " | ".join(gf.verdicts(gf.agreger([_run("live", **c.rapport())])))
    assert "ZÉRO déclenchement" in lignes
    assert "JAMAIS OBSERVÉ" in lignes                  # les quatre autres


def test_verdicts_alerte_sur_une_panne():
    c = gf.Collecteur()
    c.observer(gf.KILL_DD, etat=gf.ERREUR, motif="check_indisponible")
    assert any("ERROR" in x for x in gf.verdicts(gf.agreger([_run("live", **c.rapport())])))


def test_verdicts_compte_les_jours_ou_le_disjoncteur_AURAIT_coupe():
    """C'est LA mesure qui manquait : `coupe_circuit` conditionne son armement à ces
    jours-là, et rien ne les enregistrait."""
    c = gf.Collecteur()
    c.observer(gf.DISJONCTEUR, etat=gf.ACTIVE, aurait=True, motif="perte_du_jour")
    a = gf.agreger([_run("live", **c.rapport())])
    assert a["gardes"][gf.DISJONCTEUR]["aurait_declenche"] == 1
    assert any("aurait coupé" in x for x in gf.verdicts(a))


def test_un_seuil_ATTEINT_en_observation_n_est_pas_un_seuil_inatteignable():
    """Défaut trouvé en regardant le rapport : le disjoncteur qui AURAIT coupé deux fois
    récoltait quand même « ZÉRO déclenchement — vérifier que son seuil est atteignable ».
    Il l'a atteint : il n'a simplement pas le droit d'agir."""
    c = gf.Collecteur()
    for _ in range(12):
        c.observer(gf.DISJONCTEUR, etat=gf.ACTIVE)
    c.observer(gf.DISJONCTEUR, etat=gf.ACTIVE, aurait=True, motif="perte_du_jour")
    lignes = gf.verdicts(gf.agreger([_run("live", **c.rapport())]))
    dis = [x for x in lignes if x.startswith(gf.DISJONCTEUR)]
    assert not any("atteignable" in x for x in dis)
    assert any("aurait coupé" in x for x in dis)


def test_un_rapport_vide_dit_UNCALIBRATED_pas_zero():
    assert "UNCALIBRATED" in gf.verdicts(gf.agreger([]))[0]


def test_le_store_fait_un_aller_retour(_store_isole):
    c = gf.Collecteur()
    c.observer(gf.PORTAIL, declenche=True, effet_usd=42.0, motif="poids_ligne")
    assert _store_isole.record(c.rapport(), mode="live") is True
    runs = _store_isole.charger()
    assert len(runs) == 1 and runs[0]["mode"] == "live"
    assert runs[0]["gardes"][gf.PORTAIL]["effet_usd"] == 42.0


def test_le_store_DIT_quand_il_n_a_pas_pu_ecrire(tmp_path, monkeypatch):
    """Un enregistrement raté en silence produit un rapport qui sous-compte sans
    l'avouer — exactement ce que ce dispositif existe pour rendre visible."""
    cible = tmp_path / "interdit" / "garde_fous.json"
    monkeypatch.setattr(store, "_F", cible)
    monkeypatch.setattr(store.Path, "mkdir", lambda *a, **k: (_ for _ in ()).throw(OSError))
    assert store.record({gf.PORTAIL: {"observations": 1}}, mode="live") is False


def test_le_store_accumule_les_runs_sans_les_ecraser(_store_isole):
    """Chaque point est un INCRÉMENT, pas un cumul — l'inverse de `frais_store`."""
    c = gf.Collecteur()
    c.observer(gf.PORTAIL, declenche=True, effet_usd=10.0, motif="poids_ligne")
    _store_isole.record(c.rapport(), mode="live", horodatage="2026-09-19T10:00:00+00:00")
    _store_isole.record(c.rapport(), mode="live", horodatage="2026-09-20T10:00:00+00:00")
    runs = _store_isole.charger()
    assert len(runs) == 2
    assert gf.agreger(runs)["gardes"][gf.PORTAIL]["effet_usd"] == 20.0


def test_le_fichier_ne_contient_ni_symbole_ni_montant_de_position(_store_isole):
    """Le compte-rendu est un fichier de COMPTEURS : il n'a pas à transporter ce que
    le compte détient. Seuls des noms de règles y figurent."""
    c = gf.Collecteur()
    v = evaluer("acheter", 50_000.0, EtatCompte(100_000.0, 0.0, 0),
                _limites(max_ordre_pct=0.15))
    c.portail(v, 50_000.0)
    _store_isole.record(c.rapport(), mode="live")
    brut = json.dumps(_store_isole.charger())
    assert "taille_ordre" in brut                     # la RÈGLE, elle, doit s'y trouver
    assert "symbol" not in brut and "symbole" not in brut
    assert "detenu" not in brut and "equity" not in brut
