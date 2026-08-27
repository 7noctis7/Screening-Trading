"""Le mandat : identité stable, cosmétique hors identité, cibles de résultat
refusées."""

import dataclasses

import pytest

from packages.mandate import Mandat, depuis_dict, exiger_valide, valider


def _mandat():
    return Mandat(
        moteur="preset",
        contraintes={"drawdown_max": 0.35, "poids_max_ligne": 0.10},
        parametres={"top_k": 30, "lookback": 120, "regime_gate": True},
        donnees={"as_of_obligatoire": True},
        execution={"bande_no_trade": 0.03},
        meta={"nom": "Preset multi-actifs", "auteur": "TF"},
    )


def test_renommer_ne_change_pas_l_identite():
    """LE choix de conception. Renommer un mandat ne doit pas rompre le lien d'audit
    avec les ordres qu'il a déjà produits — sinon corriger une faute de frappe dans
    une description orpheline tout l'historique."""
    m = _mandat()
    assert m.renomme("Autre nom").identite() == m.identite()


def test_meta_entiere_hors_identite():
    m = _mandat()
    autre = m.avec(meta={"nom": "X", "description": "Y", "tags": ["a"]})
    assert autre.identite() == m.identite()


def test_changement_semantique_change_l_identite():
    m = _mandat()
    for champ, valeur in [
        ("parametres", {"top_k": 31}),
        ("contraintes", {"drawdown_max": 0.30}),
        ("execution", {"bande_no_trade": 0.05}),
        ("donnees", {"as_of_obligatoire": False}),
        ("moteur", "autre"),
    ]:
        assert m.avec(**{champ: valeur}).identite() != m.identite(), champ


def test_cible_de_resultat_refusee():
    """« Donne-moi un Sharpe de 2,3 » est une spécification par le RÉSULTAT.

    Le dépôt possède la preuve chiffrée que ce n'est pas honorable : 126 pas ne
    résolvent que ~+0,14 de Sharpe (ADR-0039), donc le système ne distingue même pas
    1,35 de 1,49. Le refus est STRUCTUREL, pas un conseil dans une docstring.
    """
    for cle in ("sharpe_cible", "cible_sharpe", "min_sortino", "target_calmar",
                "rendement", "dsr", "cible_win_rate"):
        m = Mandat(moteur="preset", contraintes={cle: 2.3})
        fautes = valider(m)
        assert any("CIBLE DE RÉSULTAT" in f for f in fautes), (cle, fautes)


def test_drawdown_max_reste_autorise():
    """Le drawdown est une CONTRAINTE qu'on subit et qu'on plafonne, pas un résultat
    qu'on commande — la distinction est le cœur du dispositif."""
    assert valider(Mandat(moteur="preset", contraintes={"drawdown_max": 0.35})) == []


def test_contrainte_inconnue_signalee():
    fautes = valider(Mandat(moteur="preset", contraintes={"truc_inconnu": 1}))
    assert any("non reconnues" in f for f in fautes)


def test_cle_inconnue_refusee_au_chargement():
    """Une clé ignorée en silence est un mandat qui ne fait pas ce qu'il dit : elle
    n'entre ni dans le comportement ni dans le hash, et l'écart ne se voit nulle
    part."""
    with pytest.raises(ValueError, match="inconnues"):
        depuis_dict({"moteur": "preset", "parametrez": {"top_k": 30}})


def test_mandat_sans_moteur_refuse():
    with pytest.raises(ValueError, match="moteur"):
        depuis_dict({"parametres": {}})


def test_round_trip_preserve_l_identite():
    m = _mandat()
    assert depuis_dict(m.vers_dict()).identite() == m.identite()


def test_round_trip_preserve_la_meta():
    m = _mandat()
    assert depuis_dict(m.vers_dict()).meta == m.meta


def test_exiger_valide_leve_et_liste_TOUT():
    """Un appelant veut toutes les fautes d'un coup, pas la première."""
    m = Mandat(moteur="", contraintes={"sharpe_cible": 2.3}, schema_version=99)
    with pytest.raises(ValueError) as e:
        exiger_valide(m)
    assert str(e.value).count("- ") >= 3


def test_mandat_immuable():
    """Une modification produit un NOUVEAU mandat : l'identité ne peut pas glisser
    sous un ordre déjà envoyé."""
    m = _mandat()
    with pytest.raises(dataclasses.FrozenInstanceError):
        m.moteur = "autre"          # type: ignore[misc]


def test_identite_reproductible_entre_processus():
    """Le hash doit être stable d'un run à l'autre — donc pas de `hash()` Python,
    qui est randomisé par PYTHONHASHSEED."""
    import subprocess
    import sys
    code = ("from packages.mandate import Mandat;"
            "print(Mandat(moteur='preset', parametres={'k': 30}).identite())")
    sorties = {subprocess.run([sys.executable, "-c", code], capture_output=True,
                              text=True, check=True).stdout.strip() for _ in range(2)}
    assert len(sorties) == 1
    assert sorties.pop() == Mandat(moteur="preset", parametres={"k": 30}).identite()
