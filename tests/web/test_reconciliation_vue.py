"""Le bloc de rapprochement : il pose l'identité, et il ne cache pas son résidu.

LA QUESTION POSÉE (18/09) : « la somme des gains/pertes de l'historique des positions,
plus le gain/perte en cours, doit bien faire le capital réel ». La réponse est non — un
réalisé et un latent sont des VARIATIONS, le capital réel est un NIVEAU — et le site
doit le montrer plutôt que de laisser un lecteur additionner deux cartes qui ne
s'additionnent pas. D'où ce bloc, sur la page où le capital réel s'affiche.

Ces tests verrouillent les trois façons dont il pourrait mentir : afficher une identité
tronquée, boucher son résidu, ou se taire quand la donnée manque.
"""

import pathlib

RACINE = pathlib.Path(__file__).resolve().parents[2]
BLOC = (RACINE / "apps" / "web" / "components"
        / "Reconciliation.tsx").read_text(encoding="utf-8")
PAGE = (RACINE / "apps" / "web" / "app" / "positions"
        / "page.tsx").read_text(encoding="utf-8")


def test_le_bloc_est_sur_la_page_qui_affiche_le_CAPITAL_REEL():
    """Ailleurs, il répondrait à une question que personne ne se pose à cet endroit."""
    assert "Capital réel" in PAGE
    assert "<Reconciliation r={data.reconciliation} />" in PAGE


def test_l_identite_est_ecrite_EN_ENTIER():
    """Tronquée, elle redevient l'intuition fausse qu'elle est censée corriger : c'est
    le terme `capital(début)` qui manque à « réalisé + latent = capital »."""
    for terme in ("capital(début)", "réalisé", "latent(fin)", "latent(début)",
                  "flux", "frais"):
        assert terme in BLOC, terme


def test_les_quatre_termes_sont_AFFICHES_pas_seulement_le_total():
    """Un total sans ses termes ne se vérifie pas : c'est une affirmation, pas un
    rapprochement."""
    for cle in ("capital_initial", "realise", "latent", "attendu", "capital_final",
                "residu"):
        assert f"r.{cle}" in BLOC, cle


def test_le_residu_est_NOMME_jamais_comble():
    """Un rapprochement qui tombe juste parce qu'on y a mis un terme d'ajustement ne
    prouve rien et masque ce qu'il fallait voir."""
    assert "écart NON expliqué" in BLOC
    assert "r.explication" in BLOC


def test_l_ecart_entre_le_PANNEAU_et_le_COMPTE_est_dit():
    """Sans ce chiffre, additionner ce qu'on voit à l'écran ne retombe jamais sur le
    compte — et rien ne dit pourquoi."""
    assert "r.realise_affiche" in BLOC
    assert "r.hors_panneau" in BLOC
    assert "import historique" in BLOC


def test_une_donnee_ABSENTE_se_dit_au_lieu_de_passer_pour_un_succes():
    """Un bloc muet se lirait comme un rapprochement réussi."""
    assert "!r.disponible" in BLOC
    assert "r.motif" in BLOC


def test_des_fenetres_differentes_sont_SIGNALEES():
    """Additionner deux périodes différentes rend le rapprochement faux en silence."""
    assert "memes_fenetres" in BLOC
    assert "r.fenetres" in BLOC
