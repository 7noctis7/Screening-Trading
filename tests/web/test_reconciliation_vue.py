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
# CE QUI EST RENDU, PAS CE QUI EST COMMENTÉ (18/09). `test_le_residu_est_NOMME` a passé
# au vert après la refonte du bloc parce que la chaîne cherchée survivait dans l'en-tête
# de commentaires, alors que l'étiquette avait changé à l'écran. Un test qui se
# satisfait d'un commentaire ne garde plus rien : on vise donc le CORPS du composant.
CORPS = BLOC.split("export function", 1)[1]


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
    for cle in ("capital_initial", "capital_final", "variation", "realise", "latent",
                "explique", "residu"):
        assert f"r.{cle}" in CORPS, cle


def test_le_RESULTAT_passe_avant_le_rapprochement():
    """CE QUI MANQUAIT (18/09). Le bloc ouvrait sur l'identité, donc la première ligne
    lue était « écart NON expliqué +2 669,06 $ » — alors que la question posée était
    « combien ai-je gagné ». Un rapprochement diagnostique le REGISTRE ; il ne remplace
    pas le résultat, il l'explique. L'ordre est donc une propriété, pas un goût."""
    assert "Résultat du compte" in CORPS
    assert CORPS.index("r.variation") < CORPS.index("r.residu"), (
        "le résultat doit être rendu AVANT le résidu")


def test_les_composantes_MENENT_a_la_variation_du_compte():
    """Lue des composantes VERS le résultat, l'identité répond d'elle-même à « 331
    trades à +0,23 $ ne font pas +1 129 $ » : les trades du robot sont une ligne sur
    quatre. Lue dans l'autre sens, elle produit un « écart » qui effraie sans rien
    expliquer."""
    for etiquette in ("ce que le registre explique", "variation réelle du compte"):
        assert etiquette in CORPS, etiquette


def test_le_residu_est_NOMME_jamais_comble():
    """Un rapprochement qui tombe juste parce qu'on y a mis un terme d'ajustement ne
    prouve rien et masque ce qu'il fallait voir."""
    assert "n'explique PAS" in CORPS, "le résidu doit porter un nom à l'écran"
    assert "r.residu" in CORPS and "r.explication" in CORPS


def test_l_ecart_entre_le_PANNEAU_et_le_COMPTE_est_dit():
    """Sans ce chiffre, additionner ce qu'on voit à l'écran ne retombe jamais sur le
    compte — et rien ne dit pourquoi."""
    assert "r.realise_affiche" in CORPS
    assert "r.hors_panneau" in CORPS
    assert "mport historique" in CORPS


def test_une_donnee_ABSENTE_se_dit_au_lieu_de_passer_pour_un_succes():
    """Un bloc muet se lirait comme un rapprochement réussi."""
    assert "!r.disponible" in CORPS
    assert "r.motif" in CORPS


def test_des_fenetres_differentes_sont_SIGNALEES():
    """Additionner deux périodes différentes rend le rapprochement faux en silence."""
    assert "memes_fenetres" in CORPS
    assert "r.fenetres" in CORPS
