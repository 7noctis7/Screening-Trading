"""Compléter les noms d'univers — la CAUSE d'un échec est l'information utile.

Confondre « le fournisseur ne connaît pas ce ticker » et « le fournisseur n'a pas répondu »
ferait conclure qu'un univers est plein de titres morts alors qu'il a seulement été
interrogé trop vite. Ces tests verrouillent la distinction.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.completer_noms_univers import INCONNU, MUET, nom_fournisseur


def _fournisseur(reponses):
    """Faux fournisseur : dict alias → (nom, cause). Compte les appels."""
    appels = []

    def faux(candidat):
        appels.append(candidat)
        return reponses.get(candidat, (None, INCONNU))

    return faux, appels


def test_un_nom_connu_est_rendu_tel_quel(monkeypatch):
    import scripts.completer_noms_univers as m
    faux, _ = _fournisseur({"AAPL": ("Apple Inc.", None)})
    monkeypatch.setattr(m, "_essayer", faux)
    assert nom_fournisseur(("AAPL", "equity")) == ("AAPL", "Apple Inc.", None)


def test_une_paire_usdc_est_resolue_par_son_ALIAS(monkeypatch):
    """yfinance ignore `AAVE/USDC` mais connaît `AAVE-USD`. Le nom doit suivre l'alias
    qui sert AUSSI à valoriser, sinon la colonne « nom » décrirait un autre instrument
    que la colonne « prix »."""
    import scripts.completer_noms_univers as m
    faux, appels = _fournisseur({"AAVE-USD": ("Aave USD", None)})
    monkeypatch.setattr(m, "_essayer", faux)
    symbole, nom, cause = nom_fournisseur(("AAVE/USDC", "crypto"))
    assert (symbole, nom, cause) == ("AAVE/USDC", "Aave USD", None)
    assert appels[0] == "AAVE-USDC" and "AAVE-USD" in appels    # l'ordre des alias est suivi


def test_un_ticker_delisté_rend_la_cause_INCONNU(monkeypatch):
    import scripts.completer_noms_univers as m
    faux, _ = _fournisseur({})
    monkeypatch.setattr(m, "_essayer", faux)
    _, nom, cause = nom_fournisseur(("CELG", "equity"))
    assert nom is None and cause == INCONNU


def test_un_silence_du_fournisseur_est_REESSAYE_puis_signalé(monkeypatch):
    """Un titre vivant mais limité en débit ne doit JAMAIS être classé comme mort."""
    import scripts.completer_noms_univers as m
    appels = []

    def muet(candidat):
        appels.append(candidat)
        return None, MUET

    monkeypatch.setattr(m, "_essayer", muet)
    monkeypatch.setattr(m.time, "sleep", lambda _s: None)
    _, nom, cause = nom_fournisseur(("BK", "equity"), essais=3)
    assert nom is None and cause == MUET
    assert appels.count("BK") == 3                    # réessayé avant d'abandonner


def test_on_n_insiste_PAS_quand_le_fournisseur_a_repondu_ne_pas_connaitre(monkeypatch):
    """Réessayer un « je ne connais pas » gaspille du temps sans rien apprendre."""
    import scripts.completer_noms_univers as m
    appels = []

    def inconnu(candidat):
        appels.append(candidat)
        return None, INCONNU

    monkeypatch.setattr(m, "_essayer", inconnu)
    nom_fournisseur(("ZZZZ", "equity"), essais=5)
    assert appels.count("ZZZZ") == 1


def test_UNE_ACTION_NE_RECOIT_JAMAIS_LE_NOM_D_UNE_CRYPTO(monkeypatch):
    """Le 07/09, `ABC` (AmerisourceBergen, action délistée) recevait « Abell Coin USD » :
    le repli `-USD`, conçu pour retrouver `ETH-USD` depuis `ETH`, trouvait une crypto. Le
    script s'apprêtait à écrire ce nom dans le dépôt. Un nom faux ne se signale pas comme
    faux : il se lit, il rassure, et il traverse toutes les vérifications suivantes."""
    import scripts.completer_noms_univers as m
    faux, appels = _fournisseur({"ABC-USD": ("Abell Coin USD", None)})
    monkeypatch.setattr(m, "_essayer", faux)
    _, nom, cause = nom_fournisseur(("ABC", "equity"))
    assert nom is None and cause == INCONNU
    assert "ABC-USD" not in appels          # l'alias crypto n'est même pas TENTÉ


def test_une_crypto_garde_bien_son_repli(monkeypatch):
    """Le garde-fou ne doit pas casser le cas qu'il protège."""
    import scripts.completer_noms_univers as m
    faux, appels = _fournisseur({"ETH-USD": ("Ethereum USD", None)})
    monkeypatch.setattr(m, "_essayer", faux)
    _, nom, _ = nom_fournisseur(("ETH", "crypto"))
    assert nom == "Ethereum USD" and "ETH-USD" in appels
