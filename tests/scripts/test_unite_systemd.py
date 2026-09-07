"""Le gabarit d'unité systemd ne doit contenir AUCUN accent grave.

Le heredoc qui l'écrit n'est pas protégé — il doit interpoler l'utilisateur, le chemin du
dépôt et la version. Bash y traite donc les accents graves comme des substitutions de
commande, y compris dans ce qui ressemble à un commentaire. Le 07/09, un commentaire
contenant « régénéré par [make services] » a relancé l'installateur RÉCURSIVEMENT sous
root, et deux unités ont été écrites au milieu de messages d'erreur.

Ce test existe parce que le même piège s'est présenté TROIS fois dans la journée : dans
`make stop`, dans la garde de démarrage, puis ici. Le repérer à l'œil ne suffit visiblement
pas.
"""
import re
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
SCRIPT = RACINE / "scripts" / "install_services.sh"


def _gabarit() -> str:
    texte = SCRIPT.read_text(encoding="utf-8")
    marque = 'cat >"/etc/systemd/system/$1.service" <<UNIT\n'
    debut = texte.index(marque) + len(marque)
    return texte[debut:texte.index("\nUNIT\n", debut)]


def test_aucun_accent_grave_dans_le_gabarit():
    gabarit = _gabarit()
    fautifs = [ligne for ligne in gabarit.splitlines() if "`" in ligne]
    assert not fautifs, "accents graves exécutables dans l'unité : " + " | ".join(fautifs)


def test_aucune_substitution_de_commande_explicite():
    """`$(...)` est tout aussi exécutable, et plus discret encore."""
    gabarit = _gabarit()
    assert "$(" not in gabarit


def test_les_variables_attendues_sont_bien_interpolees():
    """Le heredoc doit rester NON protégé : ces variables sont la raison d'être du gabarit."""
    gabarit = _gabarit()
    for variable in ("$VERSION_UNITE", "$UTILISATEUR", "$RACINE"):
        assert variable in gabarit, variable


def test_la_version_d_unite_est_un_entier_lisible():
    """`make up` compare cette valeur à celle du fichier installé : elle doit être extractible."""
    texte = SCRIPT.read_text(encoding="utf-8")
    trouve = re.search(r"^VERSION_UNITE=(\d+)$", texte, re.M)
    assert trouve and int(trouve.group(1)) >= 1


def test_killmode_mixed_n_est_pas_reintroduit():
    """`mixed` ne signale que le processus principal : les enfants gardent le port."""
    assert "KillMode=mixed" not in SCRIPT.read_text(encoding="utf-8")
