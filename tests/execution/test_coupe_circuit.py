"""Branchement du disjoncteur : perte du jour lue sur l'EQUITY, désarmé par défaut."""

import pytest

from packages.execution.coupe_circuit import arme, evaluer, variation_du_jour

HIER = [{"date": "2020-01-01", "alpaca": 60_000.0, "bitmart": 40_000.0}]


def test_la_perte_du_jour_vient_de_l_equity_pas_du_journal():
    """Le journal ne réconcilie pas avec le compte (ADR-0117). Un coupe-circuit qui
    s'appuierait dessus déclencherait sur un chiffre faux."""
    assert variation_du_jour(97_000.0, HIER) == pytest.approx(-3_000.0)
    assert variation_du_jour(101_500.0, HIER) == pytest.approx(1_500.0)


def test_un_point_du_JOUR_MEME_est_ignore():
    """Sinon on compare l'equity à elle-même — un passage antérieur du jour l'a déjà
    écrite — et la variation vaudrait toujours zéro : rien ne serait mesuré."""
    from datetime import UTC, datetime
    aujourdhui = datetime.now(UTC).date().isoformat()
    hist = [*HIER, {"date": aujourdhui, "alpaca": 97_000.0}]
    assert variation_du_jour(97_000.0, hist) == pytest.approx(-3_000.0)


def test_sans_equity_anterieure_le_disjoncteur_se_tait():
    """Premier jour : rien à comparer. Un garde-fou sans mesure ne doit pas conclure."""
    assert variation_du_jour(100_000.0, []) is None
    assert evaluer(100_000.0, [])["disponible"] is False


def test_il_OBSERVE_mais_n_agit_pas_par_defaut(monkeypatch, tmp_path):
    """LE point de ce branchement. Le déclenchement ferme les positions — le geste le
    plus destructeur du système, décidé par un composant jamais éprouvé en réel. Il
    calcule, il publie, il n'agit pas tant que QUANT_DISJONCTEUR ne l'arme pas."""
    monkeypatch.delenv("QUANT_DISJONCTEUR", raising=False)
    monkeypatch.setattr("packages.execution.coupe_circuit._ETAT",
                        tmp_path / "disjoncteur.json")
    assert arme() is False

    d = evaluer(90_000.0, HIER)                      # −10 %, très au-delà du seuil 3 %
    assert d["verrouille"] is True                   # il a bien VU
    assert d["agit"] is False                        # et il n'agit PAS
    assert d["fermer_positions"] is True             # la décision existe, non appliquée


def test_arme_il_agit(monkeypatch, tmp_path):
    """Contrôle NÉGATIF du test précédent : sans lui, `agit is False` passerait au vert
    même si l'armement était cassé et ne pouvait JAMAIS agir."""
    monkeypatch.setenv("QUANT_DISJONCTEUR", "1")
    monkeypatch.setattr("packages.execution.coupe_circuit._ETAT",
                        tmp_path / "disjoncteur.json")
    assert arme() is True
    assert evaluer(90_000.0, HIER)["agit"] is True


def test_le_verrou_SURVIT_au_processus(monkeypatch, tmp_path):
    """Le cron lance un processus neuf à chaque passage. Un état en mémoire seule
    remettrait le verrou à zéro à chaque fois — donc ne verrouillerait jamais."""
    etat = tmp_path / "disjoncteur.json"
    monkeypatch.setattr("packages.execution.coupe_circuit._ETAT", etat)
    evaluer(90_000.0, HIER)
    assert etat.exists()

    # second processus : l'equity est remontée, le verrou NE se lève PAS
    assert evaluer(100_000.0, HIER)["verrouille"] is True


def test_une_journee_calme_ne_verrouille_pas(monkeypatch, tmp_path):
    monkeypatch.setattr("packages.execution.coupe_circuit._ETAT",
                        tmp_path / "disjoncteur.json")
    d = evaluer(99_000.0, HIER)                      # −1 %, sous le seuil de 3 %
    assert d["verrouille"] is False and d["entrees_autorisees"] is True
