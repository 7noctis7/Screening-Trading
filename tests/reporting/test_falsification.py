"""Critères d'invalidation : observables, chiffrés, et opposables à la note."""

from packages.reporting.falsification import falsifieurs

ACHAT_SAIN = dict(reco="Acheter", cours=100.0, stop=92.0, ma200=88.0,
                  roce=0.18, wacc=0.09, croissance_ca=0.12,
                  drawdown_courant=-0.12, max_drawdown=-0.30)


def test_une_these_saine_publie_ses_criteres_sans_etre_invalidee():
    r = falsifieurs(**ACHAT_SAIN)
    assert r["applicable"] is True and r["invalidee"] is False
    assert len(r["criteres"]) == 5
    assert all(c["declenche"] is False for c in r["criteres"])
    assert "aucun franchi" in r["motif"]


def test_un_critere_DEJA_franchi_invalide_la_these_et_le_DIT():
    """LA règle qui empêche la section d'être décorative. Sans elle, on publierait de
    beaux critères sous une recommandation qu'ils contredisent déjà — le défaut exact
    d'un rapport dont le gestionnaire de risque REFUSE pendant que l'en-tête affiche
    « BULLISH 90 % »."""
    r = falsifieurs(**{**ACHAT_SAIN, "cours": 85.0})   # sous le stop ET la MM200
    assert r["invalidee"] is True and r["n_declenches"] == 2
    assert "DÉJÀ franchi" in r["motif"]
    declenches = [c["critere"] for c in r["criteres"] if c["declenche"]]
    assert any("stop" in c for c in declenches)
    assert any("200 jours" in c for c in declenches)


def test_un_critere_NON_CALCULABLE_n_est_pas_publie():
    """Pas de « si les fondamentaux se dégradent » : soit la donnée existe et le seuil
    est chiffré, soit le critère n'existe pas. Le mandat données-réelles, appliqué à
    la sortie."""
    r = falsifieurs(reco="Acheter", cours=100.0, stop=92.0)   # ni MM200, ni ROCE, ni CA
    libelles = [c["critere"] for c in r["criteres"]]
    assert len(libelles) == 1 and "stop" in libelles[0]
    assert r["invalidee"] is False


def test_AUCUNE_donnee_donne_UNCALIBRATED_pas_une_liste_vide_rassurante():
    """Une liste vide se lirait « rien ne peut invalider cette thèse ». C'est
    l'inverse : on ne peut rien vérifier, donc la position ne se prend pas."""
    r = falsifieurs(reco="Acheter")
    assert r["applicable"] is False and r["criteres"] == []
    assert "UNCALIBRATED" in r["motif"]
    assert "ne se prend pas" in r["motif"]


def test_le_sens_s_INVERSE_pour_une_vente():
    """Contrôle NÉGATIF : sans inversion, une note de vente publierait les critères de
    sortie d'un achat — donc déclencherait à l'envers, et de façon plausible."""
    achat = falsifieurs(**ACHAT_SAIN)
    vente = falsifieurs(reco="Vendre", cours=100.0, stop=108.0, ma200=112.0,
                        drawdown_courant=-0.12, max_drawdown=-0.30)
    assert all(c["sens"] == "sous" for c in achat["criteres"])
    prix = [c for c in vente["criteres"] if "stop" in c["critere"]
            or "200 jours" in c["critere"]]
    assert prix and all(c["sens"] == "au-dessus" for c in prix)
    assert vente["invalidee"] is False


def test_une_position_NEUTRE_se_tait():
    """Inventer une thèse à invalider là où il n'y en a pas serait de la décoration."""
    r = falsifieurs(reco="Conserver", cours=100.0, stop=92.0, ma200=88.0)
    assert r["applicable"] is False and r["criteres"] == []
    assert "aucune position à invalider" in r["motif"]


def test_la_distance_est_RELATIVE_donc_comparable():
    """« à 8 % du stop » se compare d'un titre à l'autre ; « à 4,12 $ » ne se compare
    à rien."""
    r = falsifieurs(reco="Acheter", cours=100.0, stop=92.0)
    c = r["criteres"][0]
    assert c["distance_relative"] == round((100.0 - 92.0) / 92.0, 4)


def test_le_ROCE_sous_le_WACC_ferme_la_these_de_qualite():
    """Le seul critère FONDAMENTAL chiffrable avec ce que la note calcule déjà : une
    société dont le retour sur capitaux tombe sous son coût du capital détruit de la
    valeur, quel que soit le cours."""
    r = falsifieurs(**{**ACHAT_SAIN, "roce": 0.06})     # WACC 9 %
    d = [c for c in r["criteres"] if c["declenche"]]
    assert len(d) == 1 and "ROCE" in d[0]["critere"]
    assert r["invalidee"] is True


def test_la_note_MARKDOWN_publie_la_section():
    """Le rendu doit exister, sinon le calcul est invisible — et un critère de sortie
    que personne ne lit ne ferme aucune position."""
    from packages.reporting.company_report_render import _falsification_md

    md = "\n".join(_falsification_md(falsifieurs(**ACHAT_SAIN)))
    assert "Ce qui invaliderait cette thèse" in md
    assert "| Critère | Actuel | Seuil | État |" in md
    assert "stop" in md and "ROCE" in md
    assert "FRANCHI" not in md                    # thèse saine : aucun franchi


def test_le_markdown_AVERTIT_quand_la_these_est_deja_invalidee():
    from packages.reporting.company_report_render import _falsification_md

    md = "\n".join(_falsification_md(falsifieurs(**{**ACHAT_SAIN, "cours": 85.0})))
    assert "[!danger]" in md
    assert "Ne pas prendre la position" in md
    assert md.count("⛔ **FRANCHI**") == 2


def test_une_section_inapplicable_le_DIT_au_lieu_de_disparaitre():
    """Disparaître laisserait croire que la question n'a pas été posée."""
    from packages.reporting.company_report_render import _falsification_md

    md = "\n".join(_falsification_md(falsifieurs(reco="Conserver")))
    assert "Ce qui invaliderait cette thèse" in md and "[!note]" in md


def test_le_bloc_est_present_dans_la_note_COMPLETE():
    """Bout en bout : `build_company_report` doit porter la clé, sinon le rendu ne
    trouvera rien à afficher quelle que soit la qualité du calcul."""
    from datetime import UTC, datetime

    from packages.fundamentals.models import Financials
    from packages.reporting.company_report import build_company_report

    f = Financials(symbol="TEST", as_of=datetime.now(UTC),
                   sector="Information Technology", price=25.0, shares=1e9,
                   revenue=1e10, gross_profit=6e9, ebit=2e9, ebitda=2.5e9,
                   net_income=1.5e9, total_equity=8e9, total_debt=1e9, cash=2e9,
                   fcf=1.2e9, interest_expense=5e7, revenue_growth=0.10)
    r = build_company_report(f, price_series=[10.0 + i * 0.05 for i in range(300)],
                             technical={"vs_sma200": 0.08})
    assert "falsification" in r
    assert isinstance(r["falsification"].get("criteres"), list)
