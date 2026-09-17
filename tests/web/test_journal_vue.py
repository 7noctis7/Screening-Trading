"""Le journal : les trades du robot ouverts PUIS clôturés, et ce qu'on dit du reste.

DEUX DÉCISIONS, À UN JOUR D'INTERVALLE, ET LA SECONDE REMPLACE LA PREMIÈRE.

Le 16/09 j'avais mis un filtre à trois vues, « Tout » par défaut : la page porte son
propre avertissement (« les positions perdantes encore ouvertes n'y figurent pas, ce qui
embellit le tableau »), et les lots ouverts affichés en étaient la seule preuve visible.

Le 17/09, après `make reparer-journal`, la demande a été tranchée : « historique des
positions doit montrer tous les trades pris par le robot et qui ont réellement été
ouverts puis clôturés ». C'est une DÉFINITION du contenu, pas un filtre d'affichage —
et elle est juste : un lot encore ouvert n'est pas un trade, c'est une position.

CE QUI NE CHANGE PAS POUR AUTANT, et ces tests sont là pour ça : les lots ouverts ne
disparaissent pas de la PAGE. Leur nombre et leur latent restent affichés au-dessus de
la table, et le périmètre écarté (import historique) reste chiffré. Retirer les ouverts
de la table est une définition ; les retirer de la page sans le dire ferait le palmarès
de trades soldés que la page dénonce.

La sélection se fait sur l'ORIGINE de l'enregistrement, plus sur `legacy` — cf.
`packages/execution/perimetre_journal.py`, dont les tests portent la démonstration.

Et la vraie source du bruit reste ailleurs : une vente partielle crée une ligne par
tranche (`split_id` + `qty` dans `live_roundtrip`). QQQ acheté le 07/07 à 716,69 $
apparaît plusieurs fois. Sans marque, ça se lit comme une duplication.
"""

import pathlib

PAGE = (pathlib.Path(__file__).resolve().parents[2] / "apps" / "web" / "app"
        / "journal" / "page.tsx").read_text(encoding="utf-8")


def test_la_table_lit_les_lignes_DEJA_filtrees_par_l_api():
    """Le périmètre est une décision de l'API, pas un tri du navigateur. Refiltrer ici
    ferait deux définitions du même mot, qui divergeraient au premier changement."""
    assert "const brut = (data.rows ?? [])" in PAGE
    assert 'data.rows.filter' not in PAGE


def test_aucun_filtre_de_STATUT_ne_subsiste():
    """Un sélecteur « ouvert / fermé » sur une table qui n'a plus que des fermés
    afficherait une vue vide sans rien expliquer — pire qu'absent."""
    assert "useState" not in PAGE, "plus d'état de vue : la table a un contenu unique"
    assert '"status"' not in PAGE, "la colonne Statut ne dirait plus qu'une chose"


def test_les_lots_ouverts_restent_VISIBLES_hors_de_la_table():
    """LE test de cette page. Les sortir de la table est la demande ; les faire
    disparaître ferait exactement le tableau embelli contre lequel elle met en garde."""
    assert "data.ouverts" in PAGE
    assert "st.honnete" in PAGE, "le latent des ouverts doit être affiché"
    assert "pnl_latent" in PAGE
    assert "ouverts.length" in PAGE, "leur nombre doit être dit à côté de la table"


def test_le_contrepoids_donne_les_DEUX_lectures():
    """« Fermés seuls » et « toutes positions » côte à côte : la première est vraie, la
    seconde répond à « le système gagne-t-il ? ». Publier la première seule, c'est
    laisser lire un sous-ensemble comme un total."""
    assert "expectancy_toutes_positions" in PAGE
    assert "win_rate_toutes_positions" in PAGE
    assert "expectancy_ferme" in PAGE


def test_ce_qui_est_HORS_perimetre_reste_chiffre():
    """L'import historique portait −1 647,58 $ de réalisé. Hors périmètre ne veut pas
    dire invisible : sans ce chiffre, le lecteur ne peut pas juger de ce qu'il ne voit
    pas — et un préfixe non reconnu doit se voir aussi."""
    assert "st.origines" in PAGE
    assert 'st.origines["import"]' in PAGE
    assert "NON RECONNUS" in PAGE


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


# ─── Le comparatif de l'intro accepte PLUSIEURS références
# ─────────────────────────────

COURBES = (pathlib.Path(__file__).resolve().parents[2] / "apps" / "web" / "components"
           / "intro" / "IntroCourbes.tsx").read_text(encoding="utf-8")


def test_chaque_reference_a_SA_couleur():
    """Trois courbes de la même teinte ne se comparent pas. La nôtre garde `--accent` :
    le sujet du graphique est notre performance, les indices sont des repères."""
    assert "VARS_REF" in COURBES and "REPLIS_REF" in COURBES
    assert COURBES.count('cl("--accent"') == 1


def test_une_reference_SANS_serie_n_est_pas_dessinee():
    """On ne remplace pas une série manquante par celle d'à côté, et la légende ne
    mentionne que ce qui est effectivement tracé."""
    bloc = COURBES.split("export function referencesUtiles")[1].split("\n}")[0]
    assert "filter(" in bloc and "courbe?.length" in bloc


def test_l_ancienne_forme_a_UNE_reference_reste_lue():
    """Le site statique déployé ne connaît pas encore `references` : sans ce repli, sa
    courbe de comparaison disparaîtrait jusqu'à la prochaine reconstruction."""
    bloc = COURBES.split("export function referencesUtiles")[1].split("\n}")[0]
    assert "p.reference?.length" in bloc


def test_l_ecart_est_NOMME_par_reference():
    """Avec trois courbes, un « ÉCART » anonyme ne désigne plus rien."""
    assert "vs {" in COURBES
    assert "refs.map((r) => {" in COURBES


def test_le_fondu_apparie_les_references_de_MEME_RANG():
    """Une référence nouvelle sur cette fenêtre apparaît sans fondu, plutôt que de
    sortir d'une courbe qui n'est pas la sienne."""
    bloc = COURBES.split("const rfs = bruts.map(")[1].split("});")[0]
    assert "avant.length === brut.length" in bloc
