"""Trois biais systématiques de la chaîne de valorisation, corrigés et figés.

Systématiques, pas aléatoires : ils poussent tous le classement dans le MÊME sens, donc ils ne
se compensent pas sur un univers large — ils le déforment.
"""
from datetime import datetime

import pytest

from packages.fundamentals.corporate_finance import (
    MAX_CROISSANCE_PERPETUELLE, _dcf, base_capitaux_employes, capital_employed,
    damodaran_scenarios, roce_after_tax, taux_impot,
)
from packages.fundamentals.models import Financials


def _f(**kw) -> Financials:
    base = dict(symbol="X", as_of=datetime(2026, 1, 1), sector="Tech", price=100.0,
                shares=1_000_000.0, revenue=1_000_000.0, gross_profit=400_000.0,
                ebit=200_000.0, ebitda=250_000.0, net_income=150_000.0,
                total_equity=1_000_000.0, total_debt=500_000.0, cash=100_000.0,
                fcf=120_000.0)
    base.update(kw)
    return Financials(**base)


# --- B : la croissance perpétuelle est une contrainte, pas un réglage -------------------------

def test_le_plafond_sapplique_meme_si_lappelant_passe_plus():
    """LE défaut : `terminal_growth` était un défaut d'argument, donc contournable."""
    f = _f()
    au_plafond = _dcf(f, wacc_rate=0.09, growth=0.06, terminal_growth=0.03)
    au_dessus = _dcf(f, wacc_rate=0.09, growth=0.06, terminal_growth=0.06)
    assert au_dessus == pytest.approx(au_plafond), "une croissance de 6 % a été acceptée"


def test_le_plafond_ne_bride_pas_une_hypothese_raisonnable():
    f = _f()
    prudent = _dcf(f, wacc_rate=0.09, growth=0.06, terminal_growth=0.01)
    plafond = _dcf(f, wacc_rate=0.09, growth=0.06, terminal_growth=0.03)
    assert prudent < plafond, "le plafond ne doit pas écraser les hypothèses basses"


def test_l_enjeu_est_massif_donc_le_plafond_est_le_bon_endroit():
    """Sans plafond, g 2,5 % → 5 % gonfle la valeur terminale d'environ 60 %."""
    f = _f()
    sans_plafond_25 = 1.025 / (0.09 - 0.025)
    sans_plafond_50 = 1.050 / (0.09 - 0.050)
    assert sans_plafond_50 / sans_plafond_25 > 1.5


def test_wacc_sous_le_plafond_reste_refuse():
    """wacc ≤ g donne une valeur infinie : le garde-fou d'origine doit survivre au plafonnement."""
    v = _dcf(_f(), wacc_rate=0.02, growth=0.05, terminal_growth=0.03)
    assert v != v, "wacc 2 % < g 3 % doit donner NaN"


def test_le_payload_annonce_la_croissance_reellement_utilisee():
    """Publier l'hypothèse demandée plutôt que celle retenue ferait mentir le rapport."""
    r = damodaran_scenarios(_f(), wacc_rate=0.09, base_growth=0.06, terminal_growth=0.10)
    assert r["terminal_growth"] == MAX_CROISSANCE_PERPETUELLE


def test_les_scenarios_heritent_du_plafond():
    r = damodaran_scenarios(_f(), wacc_rate=0.09, base_growth=0.06, terminal_growth=0.10)
    ref = damodaran_scenarios(_f(), wacc_rate=0.09, base_growth=0.06,
                              terminal_growth=MAX_CROISSANCE_PERPETUELLE)
    assert r["scenarios"] == ref["scenarios"]


# --- A : le bilan de clôture n'est pas un instant neutre -------------------------------------

def test_capitaux_employes_moyens_quand_la_periode_precedente_existe():
    cloture = _f(total_equity=1_000_000.0, total_debt=500_000.0, cash=100_000.0)
    precedent = _f(total_equity=1_000_000.0, total_debt=900_000.0, cash=100_000.0)
    seul = capital_employed(cloture)
    moyen = capital_employed(cloture, precedent)
    assert seul == 1_400_000.0
    assert moyen == 1_600_000.0
    assert moyen > seul, "la clôture après pic d'activité sous-estime les capitaux employés"


def test_le_roce_baisse_quand_on_moyenne_un_bilan_saisonnier():
    """Le cas du distributeur : clôture après écoulement des stocks → ROCE flatté."""
    cloture = _f(ebit=200_000.0, total_equity=1_000_000.0, total_debt=500_000.0, cash=100_000.0)
    precedent = _f(total_equity=1_000_000.0, total_debt=1_400_000.0, cash=100_000.0)
    flatte = roce_after_tax(cloture)
    honnete = roce_after_tax(cloture, precedent)
    assert flatte > honnete
    assert (flatte - honnete) / flatte > 0.15, "l'écart doit être matériel, pas cosmétique"


def test_la_base_utilisee_est_declaree():
    assert base_capitaux_employes(None) == "clôture"
    assert base_capitaux_employes(_f()) == "moyenne"


# --- D : un taux d'impôt unique biaise le classement transversal -----------------------------

def test_le_taux_dimpot_suit_la_juridiction():
    assert taux_impot(_f(currency="TWD")) == 0.20      # Taïwan (TSM)
    assert taux_impot(_f(currency="EUR")) == 0.26      # zone euro (ASML)
    assert taux_impot(_f(currency="USD")) == 0.25
    assert taux_impot(_f(currency="CHF")) == 0.15


def test_devise_inconnue_retombe_sur_le_defaut():
    """On ne devine pas une juridiction : mieux vaut un taux moyen assumé qu'un faux précis."""
    assert taux_impot(_f(currency="XXX")) == 0.25
    assert taux_impot(_f(currency=None)) == 0.25


def test_la_devise_du_cours_sert_de_repli():
    assert taux_impot(_f(currency=None, price_currency="JPY")) == 0.30


def test_deux_societes_identiques_dans_deux_pays_nont_pas_le_meme_roce():
    """C'est tout l'enjeu : sans cela, le classement qualité récompense la domiciliation."""
    tw = roce_after_tax(_f(currency="TWD"))
    ch = roce_after_tax(_f(currency="CHF"))
    assert ch > tw, "la Suisse taxe moins : à EBIT égal, le NOPAT est plus élevé"
