"""La marque « Quant Terminal » rejoue le rideau — et un rejeu REPART DE ZÉRO.

Le piège de ce mécanisme tient en une ligne : `fini` est une RÉFÉRENCE React, elle
survit
au premier passage. Un second rideau se lancerait donc bien, mais `terminer()` ne ferait
plus rien à la fin — le rideau resterait baissé sur la landing, et il faudrait
recharger la
page pour s'en sortir. C'est une panne SANS message, la famille de défauts la plus
coûteuse
de ce projet.

Second piège, plus discret : `jouer` reste VRAI d'un passage à l'autre. Une dépendance
sur
`jouer` seul ne se redéclencherait jamais — le clic serait sans effet, ce qui
ressemble à un
bouton mort. D'où le compteur `rejeu`.
"""

import pathlib

WEB = pathlib.Path(__file__).resolve().parents[2] / "apps" / "web" / "components"
GATE = (WEB / "intro" / "useIntroGate.ts").read_text(encoding="utf-8")
SEQ = (WEB / "intro" / "IntroSequence.tsx").read_text(encoding="utf-8")
NAV = (WEB / "Nav.tsx").read_text(encoding="utf-8")


# ─── La marque déclenche le rejeu, sur les DEUX barres
# ─────────────────────────────────

def test_la_marque_appelle_le_rejeu_sur_mobile_ET_sur_bureau():
    """Deux barres distinctes portent la marque. En corriger une seule donne un site qui
    se comporte autrement selon la largeur de la fenêtre, sans que rien ne le dise."""
    assert NAV.count("onClick={rejouerIntro}") == 2
    assert 'import { rejouerIntro } from "@/components/intro/useIntroGate";' in NAV


def test_la_marque_reste_un_LIEN_vers_l_accueil():
    """Le rejeu s'AJOUTE au comportement attendu d'un logo ; il ne le remplace pas."""
    for ligne in NAV.splitlines():
        if "onClick={rejouerIntro}" in ligne:
            assert 'href="/"' in ligne


def test_le_rejeu_est_annonce_a_la_souris_et_aux_lecteurs():
    """Un clic qui déclenche vingt-six secondes d'animation sans prévenir est une
    surprise, pas une fonction."""
    assert NAV.count("title=\"Rejouer la présentation") == 2


# ─── Le rejeu survit à une navigation
# ──────────────────────────────────────────────────

def test_la_demande_de_rejeu_est_un_ETAT_DE_MODULE_pas_un_simple_evenement():
    """Cliquer la marque depuis `/trades` déclenche une navigation : le rideau n'est pas
    encore monté quand le clic part, donc aucun écouteur ne peut l'entendre. Un état de
    module survit à la navigation côté client et se fait consommer à l'arrivée."""
    assert "let rejeuEnAttente = false;" in GATE
    assert "rejeuEnAttente = true;" in GATE
    assert "rejeuEnAttente = false;" in GATE.split("export function useIntroGate")[1], \
        "le drapeau doit être CONSOMMÉ par le rideau, sinon il rejouerait sans fin"


def test_le_rejeu_efface_la_marque_deja_vu():
    """Sans cela, la politique « une fois par onglet » reprendrait la main aussitôt."""
    bloc = GATE.split("export function rejouerIntro")[1].split("}")[0]
    assert "sessionStorage.removeItem" in bloc and "localStorage.removeItem" in bloc


def test_le_drapeau_est_consomme_HORS_de_la_fonction_de_mise_a_jour():
    """En mode strict, React invoque deux fois la fonction passée à `setState`. Un effet
    de bord glissé dedans se jouerait — ou se perdrait — une fois de trop."""
    corps = GATE.split("const decider = ()")[1].split("decider();")[0]
    avant_set = corps.split("setEtat")[0]
    assert "rejeuEnAttente = false;" in avant_set


# ─── Un rejeu repart de zéro
# ───────────────────────────────────────────────────────────

def test_le_compteur_rejeu_existe_parce_que_jouer_ne_change_plus():
    assert "rejeu: number" in GATE
    assert "rejeu: demande ? p.rejeu + 1 : p.rejeu" in GATE
    assert "}, [jouer, rejeu]);" in SEQ, "sans `rejeu`, l'effet ne repartirait pas"


def test_un_rejeu_remet_TOUT_a_zero_y_compris_la_reference_fini():
    """`fini.current` oublié = rideau qui ne se lève plus à la fin du second passage."""
    bloc = SEQ.split("if (!jouer) return;")[1].split("}, [jouer, rejeu]);")[0]
    for remise in ("fini.current = false;", "setSortie(false);", "setReveal(false);",
                   "setBeat({ i: 0, p: 0 });", "setAvance(0);",
                   "setAttenteEcoulee(false);", "setMonte(true);"):
        assert remise in bloc, f"remise à zéro manquante au rejeu : {remise}"


# ─── Les bornes de fenêtre sont DESSINÉES, et lues sans fuseau ───────────────────────

DRAW = (WEB / "intro" / "introCourbeDraw.ts").read_text(encoding="utf-8")
COURBES = (WEB / "intro" / "IntroCourbes.tsx").read_text(encoding="utf-8")


def test_les_deux_bornes_de_la_fenetre_sont_dessinees():
    """« +142 % sur 10 ans » ne dit pas DE QUAND À QUAND."""
    assert "export function bornesDates(" in DRAW
    assert "bornesDates(ctx, c, d.debut, d.fin, cFg, aRepere)" in COURBES


def test_la_date_est_lue_A_LA_MAIN_jamais_par_Date():
    """`new Date("2016-05-19")` vaut minuit UTC : dans un fuseau négatif,
    `toLocaleDateString` afficherait le 18/05. La période MESURÉE changerait alors
    selon l'endroit d'où on regarde le site."""
    bloc = DRAW.split("export function dateCourte")[1].split("\n}")[0]
    assert "new Date" not in bloc and "toLocale" not in bloc
    assert "exec(iso" in bloc


def test_une_date_illisible_ne_s_invente_pas():
    """Rendre « » plutôt qu'une date approchée : les bornes ne s'affichent alors pas,
    ce qui se voit — contrairement à une date fausse."""
    bloc = DRAW.split("export function bornesDates")[1].split("\n}")[0]
    assert "if (!d || !f) return;" in bloc


def test_les_bornes_apparaissent_avec_les_reperes_pas_pendant_la_deformation():
    """Des dates qui sauteraient d'un coup pendant que le tracé glisse d'une fenêtre à
    la suivante se liraient comme une erreur d'affichage."""
    assert "bornesDates(ctx, c, d.debut, d.fin, cFg, aRepere)" in COURBES
