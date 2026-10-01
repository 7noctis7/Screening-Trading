"""Portail de risque pré-trade — la dernière barrière avant le courtier.

Contexte du 25/08 : `RiskEngine` n'était instancié que dans `scripts/demo_*.py`. Le chemin de
production (`run_live.py`) envoyait au courtier le montant décidé par la stratégie, sans veto
par ordre. Ces tests fixent le contrat de la barrière qui manquait.
"""

import pytest

from packages.risk.order_gate import EtatCompte, Limites, evaluer, ligne_journal

LIM = Limites(max_poids_ligne=0.20, max_positions=10, max_ordre_pct=0.15, max_exposition=1.0)


def _etat(equity=100_000.0, expo=50_000.0, n=5, ligne=0.0):
    return EtatCompte(equity=equity, exposition_brute=expo, n_positions=n, detenu_ligne=ligne)


def test_ordre_dans_les_limites_passe_intact():
    v = evaluer("acheter", 5_000, _etat(), LIM)
    assert v.autorise and v.montant == 5_000 and v.regle == "ok" and not v.reduit


# --- LE PORTAIL NE PEUT QUE RÉDUIRE ---------------------------------------------------------

def test_ordre_trop_gros_est_reduit_jamais_refuse():
    v = evaluer("acheter", 50_000, _etat(), LIM)
    assert v.autorise and v.montant == 15_000 and v.regle == "taille_ordre"


def test_poids_de_ligne_plafonne_en_tenant_compte_du_deja_detenu():
    """18 000 $ déjà détenus, plafond 20 % de 100 000 → il reste 2 000 $ de marge."""
    v = evaluer("acheter", 10_000, _etat(ligne=18_000), LIM)
    assert v.autorise and v.montant == 2_000 and v.regle == "poids_ligne"


def test_ligne_deja_au_plafond_est_refusee():
    v = evaluer("acheter", 5_000, _etat(ligne=20_000), LIM)
    assert not v.autorise and v.regle == "poids_ligne"


def test_anti_levier_le_brut_ne_depasse_jamais_l_equity():
    v = evaluer("acheter", 20_000, _etat(expo=95_000), LIM)
    assert v.autorise and v.montant == 5_000 and v.regle == "exposition_brute"
    assert evaluer("acheter", 1_000, _etat(expo=100_000), LIM).autorise is False


def test_le_plafond_le_plus_contraignant_l_emporte():
    """Marge ordre 15 000, marge ligne 2 000, marge brute 10 000 → 2 000 gagne."""
    v = evaluer("acheter", 14_000, _etat(expo=90_000, ligne=18_000), LIM)
    assert v.montant == 2_000 and v.regle == "poids_ligne"


def test_le_portail_n_augmente_jamais_un_ordre():
    for demande in (1.0, 100.0, 5_000.0, 999_999.0):
        v = evaluer("acheter", demande, _etat(), LIM)
        assert v.montant <= demande + 1e-9


# --- RÉDUIRE LE RISQUE PASSE TOUJOURS -------------------------------------------------------

@pytest.mark.parametrize("action", ["alleger", "solder", "vendre"])
def test_un_desengagement_n_est_jamais_bloque(action):
    """Un portail qui refuse une vente AUGMENTE le risque. Même compte saturé, même equity
    au plafond, même nombre de positions dépassé : le désengagement passe."""
    v = evaluer(action, 50_000, _etat(expo=200_000, n=99, ligne=90_000), LIM)
    assert v.autorise and v.montant == 50_000


def test_une_liquidation_passe_meme_etiquetee_acheter():
    v = evaluer("acheter", 900, _etat(expo=200_000, n=99), LIM, liquidation=True)
    assert v.autorise and v.montant == 900


# --- INCONNU ≠ ZÉRO ------------------------------------------------------------------------

def test_equity_illisible_refuse_tout_achat():
    for eq in (0.0, -1.0):
        v = evaluer("acheter", 1_000, _etat(equity=eq), LIM)
        assert not v.autorise and v.regle == "equity_inconnue"


def test_equity_illisible_laisse_QUAND_MEME_sortir():
    """Une sortie part en QUANTITÉ : elle n'a pas besoin qu'on sache dimensionner. Refuser de
    vendre parce que le courtier n'a pas renvoyé l'equity enfermerait la position le jour
    précis où l'on veut sortir."""
    assert evaluer("solder", 1_000, _etat(equity=0.0), LIM).autorise is True
    assert evaluer("acheter", 1_000, _etat(equity=0.0), LIM, liquidation=True).autorise is True


# --- NOMBRE DE POSITIONS -------------------------------------------------------------------

def test_plafond_de_positions_bloque_l_ouverture_pas_le_renforcement():
    plein = _etat(n=10, ligne=0.0)
    assert evaluer("acheter", 1_000, plein, LIM).autorise is False       # nouvelle ligne
    renfort = _etat(n=10, ligne=5_000.0)
    assert evaluer("acheter", 1_000, renfort, LIM).autorise is True      # ligne existante


# --- LIMITES : risk.yaml + override ENV explicite ------------------------------------------

def _clear_quant_risk_env(monkeypatch):
    for k in (
        "QUANT_RISK_MAX_WEIGHT",
        "QUANT_RISK_MAX_WEIGHT_BASKET",
        "QUANT_RISK_MAX_POSITIONS",
        "QUANT_RISK_MAX_ORDER_PCT",
        "QUANT_RISK_MAX_GROSS",
    ):
        monkeypatch.delenv(k, raising=False)


def test_sans_env_limites_suivent_risk_yaml(monkeypatch):
    """Sans QUANT_RISK_* → plafonds = config/risk.yaml (20, 0.10, 0.60, 0.15, 1.0)."""
    _clear_quant_risk_env(monkeypatch)
    lim = Limites.depuis_env()
    assert lim.max_positions == 20
    assert lim.max_poids_ligne == 0.10
    assert lim.max_poids_ligne_panier == 0.60
    assert lim.max_ordre_pct == 0.15
    assert lim.max_exposition == 1.0


def test_env_n_override_que_la_cle_definie(monkeypatch):
    """QUANT_RISK_MAX_POSITIONS=99 override positions only ; le reste reste yaml."""
    _clear_quant_risk_env(monkeypatch)
    monkeypatch.setenv("QUANT_RISK_MAX_POSITIONS", "99")
    lim = Limites.depuis_env()
    assert lim.max_positions == 99
    assert lim.max_poids_ligne == 0.10
    assert lim.max_poids_ligne_panier == 0.60
    assert lim.max_ordre_pct == 0.15
    assert lim.max_exposition == 1.0


def test_depuis_yaml_temp_file_reflete_max_positions(tmp_path):
    """Changement YAML via fichier temporaire → Limites.depuis_yaml suit."""
    yaml_text = """portfolio:
  max_positions: 7
  max_exposure_per_asset_pct: 0.10
  max_weight_basket_pct: 0.60
  max_order_pct: 0.15
  max_gross_exposure: 1.0
"""
    f = tmp_path / "risk.yaml"
    f.write_text(yaml_text)
    lim = Limites.depuis_yaml(f)
    assert lim.max_positions == 7
    assert lim.max_poids_ligne == 0.10
    assert lim.max_ordre_pct == 0.15


def test_yaml_illisible_replie_sur_constantes_module(tmp_path):
    """YAML manquant → constantes module (dégrade sûre, jamais soft-open)."""
    lim = Limites.depuis_yaml(tmp_path / "absent.yaml")
    assert lim.max_positions == 40
    assert lim.max_poids_ligne == 0.20
    assert lim.max_poids_ligne_panier == 0.60
    assert lim.max_ordre_pct == 0.15
    assert lim.max_exposition == 1.0


def test_limites_viennent_de_l_environnement(monkeypatch):
    """ENV non vide override le YAML (compat historique)."""
    _clear_quant_risk_env(monkeypatch)
    monkeypatch.setenv("QUANT_RISK_MAX_WEIGHT", "0.05")
    monkeypatch.setenv("QUANT_RISK_MAX_POSITIONS", "3")
    lim = Limites.depuis_env()
    assert lim.max_poids_ligne == 0.05 and lim.max_positions == 3


def test_une_limite_illisible_retombe_sur_le_defaut(monkeypatch):
    """Une faute de frappe dans .env ne doit pas désactiver silencieusement un garde-fou."""
    _clear_quant_risk_env(monkeypatch)
    monkeypatch.setenv("QUANT_RISK_MAX_WEIGHT", "vingt pour cent")
    monkeypatch.setenv("QUANT_RISK_MAX_GROSS", "-3")
    lim = Limites.depuis_env()
    # Défaut = risk.yaml (pas les constantes module) quand ENV illisible.
    assert lim.max_poids_ligne == 0.10 and lim.max_exposition == 1.00


def test_montant_nul_refuse():
    assert evaluer("acheter", 0.0, _etat(), LIM).autorise is False


def test_journal_explique_chaque_decision():
    """« Pourquoi cet ordre a-t-il été réduit ? » doit avoir une réponse écrite."""
    v = evaluer("acheter", 50_000, _etat(), LIM)
    ligne = ligne_journal("NVDA", "acheter", 50_000, v)
    assert "NVDA" in ligne and "RÉDUIT" in ligne and "taille_ordre" in ligne
    refus = ligne_journal("NVDA", "acheter", 1_000, evaluer("acheter", 1_000, _etat(equity=0), LIM))
    assert "REFUSÉ" in refus and "equity_inconnue" in refus


# ─── La trace doit ÉTABLIR ce qu'elle affirme (constaté le 15/09) ──────────────────────

def test_une_reduction_inferieure_au_dollar_reste_visible():
    """« 796 $ réduit à 796 $ » : la ligne affirmait une réduction et montrait deux
    nombres égaux. Le cas réel du passage VPS du 15/09 sur BCH/USD."""
    from packages.risk.order_gate import EtatCompte, Limites, evaluer, ligne_journal
    lim = Limites()
    etat = EtatCompte(equity=100_000.0, exposition_brute=99_204.40, n_positions=20)
    v = evaluer("acheter", 796.40, etat, lim)
    assert v.reduit and v.montant == 795.60
    assert "796.40 $ réduit à 795.60 $" in v.motif
    ligne = ligne_journal("BCH/USD", "acheter", 796.40, v)
    assert "796.40$" in ligne and "795.60$" in ligne


def test_une_reduction_franche_garde_l_unite():
    """Quand le dollar suffit, rien ne change — on n'encombre pas la trace de centimes."""
    from packages.risk.order_gate import EtatCompte, Limites, evaluer, ligne_journal
    v = evaluer("acheter", 20_000.0,
                EtatCompte(equity=100_000.0, exposition_brute=0.0, n_positions=3), Limites())
    assert "20000 $ réduit à 15000 $" in v.motif
    assert ".00$" not in ligne_journal("AAPL", "acheter", 20_000.0, v)


def test_un_ordre_accepte_garde_le_format_entier():
    """La précision au centime ne s'applique QU'aux réductions : un OK n'a rien à montrer."""
    from packages.risk.order_gate import EtatCompte, Limites, evaluer, ligne_journal
    v = evaluer("acheter", 1_000.0,
                EtatCompte(equity=100_000.0, exposition_brute=0.0, n_positions=3), Limites())
    assert not v.reduit
    assert "1000$" in ligne_journal("AAPL", "acheter", 1_000.0, v)


def test_le_plafond_lui_meme_est_inchange():
    """On corrige ce que la trace DIT, jamais ce que le portail FAIT : le montant retenu
    reste exactement le plafond, au centime près."""
    from packages.risk.order_gate import EtatCompte, Limites, evaluer
    etat = EtatCompte(equity=100_000.0, exposition_brute=99_204.40, n_positions=20)
    assert evaluer("acheter", 796.40, etat, Limites()).montant == 795.60
    # …et un montant SOUS le plafond passe entier, sans mention de réduction.
    v = evaluer("acheter", 700.0, etat, Limites())
    assert v.montant == 700.0 and not v.reduit
