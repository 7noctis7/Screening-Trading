"""Le contrat de sortie du LLM. Un signal presque correct vaut mieux qu'une exception,
mais tout ce qu'on a dû corriger doit rester visible."""

import pytest

from packages.nlp.schemas import (
    HORIZONS,
    RESUME_MAX,
    SCHEMA,
    SENTIMENTS,
    SignalNLP,
    modele_pydantic,
    repli,
    valider,
)

BON = {"ticker": "AAPL", "sentiment": "BULLISH", "confidence_score": 0.7,
       "impact_horizon": "SWING", "catalyst_summary": "Résultats au-dessus du consensus."}


def test_un_signal_conforme_passe_intact():
    s = valider(BON, "AAPL")
    assert (s.sentiment, s.confiance, s.horizon) == ("BULLISH", 0.7, "SWING")
    assert not s.repli and s.incidents == ()


# ─── Ce que le schéma impose au modèle ─────────────────────────────────────────────────

def test_le_schema_interdit_les_champs_surnumeraires():
    """Sans `additionalProperties: false`, un modèle bavard ajoute des champs qu'on
    accepterait sans les avoir demandés."""
    assert SCHEMA["additionalProperties"] is False


def test_le_schema_borne_la_confiance():
    c = SCHEMA["properties"]["confidence_score"]
    assert c["minimum"] == 0.0 and c["maximum"] == 1.0


def test_le_schema_et_le_code_partagent_les_memes_enums():
    """Le seul garde-fou contre une divergence entre ce qu'on DEMANDE et ce qu'on ACCEPTE."""
    assert SCHEMA["properties"]["sentiment"]["enum"] == list(SENTIMENTS)
    assert SCHEMA["properties"]["impact_horizon"]["enum"] == list(HORIZONS)


def test_les_cinq_champs_sont_tous_requis():
    assert set(SCHEMA["required"]) == set(SCHEMA["properties"])
    assert len(SCHEMA["required"]) == 5


def test_le_schema_ne_demande_PAS_sa_propre_provenance():
    """Laisser le modèle renseigner quel modèle il est, ou s'il est un repli, serait lui
    demander de se noter lui-même."""
    for interdit in ("modele", "version_invite", "repli", "confidence_calibrated"):
        assert interdit not in SCHEMA["properties"]


# ─── Tolérance, mais traçable ──────────────────────────────────────────────────────────

def test_un_sentiment_inconnu_devient_neutre_ET_annule_la_confiance():
    """Garder 0,9 de confiance sur un sentiment qu'on a réécrit ferait porter la confiance
    sur une classification qui n'est plus celle du modèle."""
    s = valider({**BON, "sentiment": "HAUSSIER", "confidence_score": 0.9}, "AAPL")
    assert s.sentiment == "NEUTRAL" and s.confiance == 0.0
    assert any("sentiment inconnu" in i for i in s.incidents)


def test_une_confiance_hors_bornes_est_bornee_et_signalee():
    s = valider({**BON, "confidence_score": 1.4}, "AAPL")
    assert s.confiance == 1.0 and any("hors bornes" in i for i in s.incidents)


def test_une_confiance_illisible_vaut_zero():
    for mauvaise in ("beaucoup", None, [1]):
        s = valider({**BON, "confidence_score": mauvaise}, "AAPL")
        assert s.confiance == 0.0 and s.incidents


def test_nan_en_confiance_vaut_zero():
    s = valider({**BON, "confidence_score": float("nan")}, "AAPL")
    assert s.confiance == 0.0 and any("NaN" in i for i in s.incidents)


def test_un_horizon_inconnu_retombe_sur_immediate():
    s = valider({**BON, "impact_horizon": "DEMAIN"}, "AAPL")
    assert s.horizon == "IMMEDIATE" and any("horizon inconnu" in i for i in s.incidents)


def test_le_ticker_demande_l_emporte_sur_celui_renvoye():
    """Accepter le ticker du modèle attribuerait une nouvelle à une valeur qu'on
    n'analysait pas."""
    s = valider({**BON, "ticker": "MSFT"}, "AAPL")
    assert s.ticker == "AAPL"
    assert any("MSFT" in i and "AAPL" in i for i in s.incidents)


def test_un_resume_trop_long_est_tronque_et_signale():
    s = valider({**BON, "catalyst_summary": "x" * (RESUME_MAX + 50)}, "AAPL")
    assert len(s.resume) == RESUME_MAX and any("tronqué" in i for i in s.incidents)


def test_la_casse_du_ticker_est_normalisee():
    assert valider(BON, "aapl").ticker == "AAPL"


# ─── Ce qui déclenche un repli plutôt qu'une tolérance ─────────────────────────────────

def test_un_champ_manquant_donne_un_repli_qui_NOMME_le_champ():
    s = valider({k: v for k, v in BON.items() if k != "sentiment"}, "AAPL")
    assert s.repli and "sentiment" in s.resume


def test_une_reponse_qui_n_est_pas_un_objet_donne_un_repli():
    for mauvais in ("texte", [1, 2], None, 42):
        assert valider(mauvais, "AAPL").repli


# ─── Le repli ──────────────────────────────────────────────────────────────────────────

def test_le_repli_est_neutre_a_confiance_nulle_et_se_declare():
    """Un repli silencieux serait indistinguable d'une classification neutre légitime —
    et un taux de neutres anormal ne voudrait plus rien dire."""
    r = repli("TSLA")
    assert r.sentiment == "NEUTRAL" and r.confiance == 0.0
    assert r.repli is True and r.neutre and "FALLBACK" in r.resume


def test_la_confiance_n_est_jamais_declaree_calibree_par_defaut():
    """« 0,85 » ne signifie pas « 85 % de chances » tant que le Brier n'a pas été mesuré."""
    assert valider(BON, "AAPL").calibree is False
    assert SignalNLP(ticker="X").calibree is False


# ─── Vue Pydantic (optionnelle) ────────────────────────────────────────────────────────

def test_la_vue_pydantic_decrit_le_meme_contrat():
    M = modele_pydantic()
    if M is None:
        pytest.skip("pydantic absent — environnement allégé")
    champs = set(M.model_fields)
    assert champs == set(SCHEMA["properties"]), "pydantic et SCHEMA ont divergé"
    genere = M.model_json_schema()
    assert set(genere["required"]) == set(SCHEMA["required"])
