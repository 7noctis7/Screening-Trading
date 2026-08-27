"""Le harnais de pureté doit ATTRAPER les défauts réels du dépôt, pas seulement passer.

Un test qui vérifie qu'un moteur pur est déclaré pur ne prouve presque rien. Chaque
test ci-dessous confronte le harnais à un moteur DÉLIBÉRÉMENT défaillant, reproduisant
un défaut qui a réellement coûté au dépôt.
"""

import os

from packages.mandate.purete import (
    VARIABLES_SUSPECTES,
    auditer,
    verifier_determinisme,
    verifier_equivalence,
    verifier_independance_environnement,
)

PUR = {"AAPL": 0.5, "MSFT": 0.5}


def test_moteur_pur_passe():
    assert auditer(lambda: dict(PUR)) == []


def test_non_determinisme_attrape():
    import random
    assert verifier_determinisme(lambda: {"A": random.random()})


def test_dependance_a_l_environnement_attrapee():
    """LE défaut du 26/08 : `QUANT_LIVE_LITE=1` coupait `fundamentals`, donc `quality`
    était vide, donc la SÉLECTION D'UNIVERS changeait. Une variable d'environnement
    décidait quelles actions acheter, et aucune configuration ne le disait."""
    def moteur():
        return {"A": 1.0} if os.environ.get("QUANT_LIVE_LITE") == "1" else dict(PUR)
    fautes = verifier_independance_environnement(moteur)
    assert fautes and "DÉPEND DE L'ENVIRONNEMENT" in fautes[0]


def test_environnement_restaure_apres_verification():
    """Le harnais bouscule l'environnement : s'il ne le restaure pas exactement, il
    contamine les tests suivants — un mode de panne pire que le défaut qu'il cherche."""
    avant = {v: os.environ.get(v) for v in VARIABLES_SUSPECTES}
    os.environ["QUANT_LIVE_LITE"] = "temoin"
    try:
        verifier_independance_environnement(lambda: dict(PUR))
        assert os.environ["QUANT_LIVE_LITE"] == "temoin"
    finally:
        for v, val in avant.items():
            os.environ.pop(v, None) if val is None else os.environ.__setitem__(v, val)


def test_variable_absente_reste_absente():
    """Cas limite : une variable NON définie avant doit le rester après."""
    os.environ.pop("QUANT_IGNORE_SESSION", None)
    verifier_independance_environnement(lambda: dict(PUR))
    assert "QUANT_IGNORE_SESSION" not in os.environ


def test_divergence_des_chemins_attrapee():
    """La propriété que #347, #352 et #353 ont rétablie une par une, à la main."""
    fautes = verifier_equivalence(lambda: dict(PUR), lambda: {"AAPL": 0.5, "MSFT": 0.4})
    assert fautes and "DIVERGENCE" in fautes[0]


def test_chemins_equivalents_passent():
    assert verifier_equivalence(lambda: dict(PUR), lambda: dict(PUR)) == []


def test_bruit_flottant_infime_tolere():
    """On compare des DÉCISIONS, pas le dernier bit d'un flottant : une réassociation
    d'opérations ne doit pas faire échouer le test pour un écart qui ne change aucun
    ordre envoyé."""
    assert verifier_equivalence(lambda: {"A": 0.1 + 0.2}, lambda: {"A": 0.3}) == []


def test_ecart_significatif_non_tolere():
    """La tolérance ne doit pas avaler un écart qui change un ordre."""
    assert verifier_equivalence(lambda: {"A": 0.100}, lambda: {"A": 0.101})


def test_moteur_qui_leve_est_signale_et_non_declare_pur():
    """Un moteur qui explose ne doit pas passer pour déterministe."""
    def moteur():
        raise RuntimeError("données manquantes")
    fautes = verifier_determinisme(moteur)
    assert fautes and "RuntimeError" in fautes[0]
