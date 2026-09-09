"""Notes d'analyse : à qui elles s'appliquent, et sous quel nom de fichier."""

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "_gr", Path(__file__).resolve().parents[2] / "scripts" / "generate_reports.py")
_gr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_gr)


def test_une_paire_crypto_n_a_pas_de_bilan_donc_pas_de_note():
    """Vernimmen et Damodaran s'appliquent à une SOCIÉTÉ. Le 09/09, `make reports` a
    interrogé Yahoo pour ZEC/USDC, VET/USDC et LTC/USDC : trois erreurs 500/502 dont
    la page HTML complète a inondé le terminal, puis un plantage. Trois notes perdues
    pour trois analyses qui n'auraient rien voulu dire."""
    for pair in ("ZEC/USDC", "BTC-USD", "ETH-USDT", "SOL-USDC"):
        assert _gr._analysable(pair) is False, pair


def test_les_ACTIONS_restent_analysables_y_compris_hors_US():
    """Contrôle NÉGATIF : un filtre trop large retirerait des sociétés réelles, et
    le run paraîtrait propre en produisant moins de notes."""
    for sym in ("AAPL", "BRK.B", "ASML.AS", "SHELL.AS", "MC.PA", "0700.HK"):
        assert _gr._analysable(sym) is True, sym


def test_le_filtre_porte_sur_la_FORME_pas_sur_une_liste():
    """Une liste devrait être tenue à jour à chaque ajout d'actif ; la forme, non.
    Un jeton inconnu au format paire est écarté sans qu'on ait rien à déclarer."""
    assert _gr._analysable("XYZAB/USDC") is False
    assert _gr._analysable("") is False


def test_le_nom_de_fichier_ne_cree_pas_de_SOUS_DOSSIER():
    """La cause exacte du plantage : `note_ZEC/USDC.html` désigne un fichier dans un
    dossier `note_ZEC` qui n'existe pas."""
    assert "/" not in _gr._nom_fichier("ZEC/USDC")
    assert _gr._nom_fichier("ZEC/USDC") == "ZEC_USDC"


def test_un_point_reste_LISIBLE_dans_le_nom():
    """`BRK.B` et `ASML.AS` ne doivent pas devenir `BRK_B` : le point est valide dans
    un nom de fichier, et le ticker doit rester reconnaissable dans le dossier."""
    assert _gr._nom_fichier("BRK.B") == "BRK.B"
    assert _gr._nom_fichier("ASML.AS") == "ASML.AS"


def test_le_bruit_reseau_est_MUSELE_a_l_import():
    """yfinance ne journalise pas une erreur, il DÉVERSE la page HTML du serveur : cent
    lignes de « sad panda » Yahoo pour un 502 sur IBM, au milieu de la liste des notes.
    Le run devient illisible et les vraies lignes se perdent. `dump_static` portait déjà
    ce silence ; ce script, qui appelle les mêmes fournisseurs, ne l'avait pas."""
    import logging
    for nom in ("yfinance", "urllib3", "peewee"):
        assert logging.getLogger(nom).level >= logging.CRITICAL, nom


def test_les_DEUX_scripts_batch_partagent_le_silence():
    """Le même remède au même endroit. Sans ce contrôle, un troisième script batch
    réintroduirait le déversement sans que rien ne le signale."""
    from pathlib import Path
    racine = Path(__file__).resolve().parents[2] / "scripts"
    for nom in ("generate_reports.py", "dump_static.py"):
        src = (racine / nom).read_text(encoding="utf-8")
        assert '"yfinance"' in src and "CRITICAL" in src, nom
