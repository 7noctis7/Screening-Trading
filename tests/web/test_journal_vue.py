"""Le journal des round-trips : on SÉPARE les lots ouverts, on ne les supprime pas.

LA QUESTION POSÉE LE 17/09 : « ce serait préférable de ne garder que l'historique des
trades ouverts ET fermés, non ? » L'intuition sur la confusion est juste, le remède non.

Cette page porte son propre avertissement : « Les positions perdantes encore ouvertes
n'y
figurent pas, ce qui embellit le tableau. » Les lots ouverts affichés sont la seule
preuve
VISIBLE de ce biais. Les retirer ferait de la page un palmarès de trades soldés —
exactement ce qu'elle dénonce. D'où un filtre qui montre tout par défaut.

Et la vraie source du bruit est ailleurs : une vente partielle crée une ligne par
tranche
(`split_id` + `qty` dans `live_roundtrip`) et laisse le reliquat ouvert. QQQ acheté le
07/07
à 716,69 $ apparaît trois fois — deux sorties et un reliquat. Sans marque, ça se lit
comme
une duplication.
"""

import pathlib

PAGE = (pathlib.Path(__file__).resolve().parents[2] / "apps" / "web" / "app"
        / "journal" / "page.tsx").read_text(encoding="utf-8")


def test_la_vue_par_defaut_montre_TOUT():
    """Masquer par défaut publierait le palmarès que l'avertissement dénonce."""
    assert 'useState<"tout" | "fermé" | "ouvert">("tout")' in PAGE


def test_les_trois_vues_existent_et_sont_comptees():
    """Un filtre dont on ne voit pas ce qu'il cache est un oubli, pas un filtre."""
    for etiquette in ("Tout (", "Round-trips fermés (", "Lots ouverts ("):
        assert etiquette in PAGE


def test_la_vue_FERMES_avertit_de_ce_qu_elle_masque():
    """C'est la vue dangereuse : elle donne exactement le tableau embelli contre lequel
    la page met en garde. Elle doit le DIRE tant qu'elle est active."""
    bloc = PAGE.split('vue === "fermé" && (')[1].split(")}")[0]
    assert "vue partielle" in bloc
    assert "ouverts" in bloc and "perdants" in bloc


def test_aucune_ligne_n_est_supprimee_du_jeu_de_donnees():
    """Le filtre porte sur l'AFFICHAGE. L'export CSV et les compteurs doivent continuer
    de décrire l'ensemble — sinon le filtre devient une amputation silencieuse."""
    assert "const toutes = brut.map(" in PAGE
    assert "toutes.length" in PAGE, "les compteurs portent sur TOUT, pas sur la vue"


def test_les_tranches_d_un_meme_lot_sont_MARQUEES():
    """Une vente partielle n'est pas un doublon. Sans marque, trois lignes QQQ au même
    prix d'entrée se lisent comme un bug d'affichage."""
    assert "fractionne" in PAGE
    assert "fractionné" in PAGE
    cle = '`${r.symbol}|${r.venue}|${r.entry_ts}|${r.entry_price}`'
    assert PAGE.count(cle) == 2, "la clé sert au comptage ET à la marque"


def test_la_marque_explique_ce_qu_elle_signifie():
    """Un symbole sans explication déplace la question au lieu d'y répondre."""
    assert "PLUSIEURS tranches" in PAGE
    assert "Ce ne sont pas des doublons" in PAGE
