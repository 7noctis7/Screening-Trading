"""Rien ne doit finir hors de l'écran d'un téléphone, sans moyen d'y accéder.

MESURE du 2026-09-07, Chromium à 390 px de large, sur les pages réelles :

    ancien CSS →  365 éléments hors écran ET injoignables (aucun parent ne défile)
    nouveau    →    0

Le pire cas était `/fundamentals` : le tableau dépassait de **492 px**, soit environ la
moitié de ses quatorze colonnes — « Solidité », « Risque de faillite », « Tendance du
cours », « Note d'ensemble » et « Avis » étaient définitivement hors d'atteinte. Rien ne
le signalait : le tableau semblait simplement s'arrêter.

La cause n'était pas un tableau en particulier. C'était la RENCONTRE de deux règles :

  1. `html, body { overflow-x:clip }` — le garde-fou anti-débordement latéral. `clip`
     coupe SANS créer de zone défilable : ce qui dépasse n'est pas atteignable, même au
     doigt, même par script.
  2. des tableaux larges posés hors de tout conteneur `overflow-x-auto`.

Chacune est raisonnable seule. Ensemble, elles font disparaître du contenu en silence.

Envelopper les quatorze tableaux fautifs à la main aurait marché *ce jour-là* : le
quinzième, écrit le mois suivant, ramenait le bug. La correction est donc STRUCTURELLE —
sur mobile, tout `<table>` devient son propre conteneur de défilement — et ce test garde
cette règle en place. Le supprimer, c'est rendre les colonnes de droite inaccessibles.

Vérifié à la mesure au moment d'écrire la règle : en-tête et corps restent alignés au
pixel, et un tableau étroit continue de remplir sa carte sans défiler.
"""

from __future__ import annotations

import re
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
CSS = RACINE / "apps" / "web" / "app" / "globals.css"


def _bloc_mobile(css: str) -> str:
    """Le contenu du `@media (max-width: 640px)`, accolades équilibrées."""
    debut = css.index("@media (max-width: 640px)")
    i = css.index("{", debut)
    profondeur, j = 0, i
    while j < len(css):
        if css[j] == "{":
            profondeur += 1
        elif css[j] == "}":
            profondeur -= 1
            if profondeur == 0:
                return css[i + 1 : j]
        j += 1
    raise AssertionError("bloc @media non refermé")


def test_les_tableaux_defilent_dans_eux_memes_sur_mobile() -> None:
    bloc = _bloc_mobile(CSS.read_text(encoding="utf-8"))
    # `table` comme sélecteur entier : ni `.card table`, ni `datatable`.
    regle = re.search(r"(?<![\w.\-#\[])table\s*\{([^}]*)\}", bloc, re.S)
    assert regle, (
        "Plus de règle `table` dans le bloc mobile : les tableaux larges redeviennent "
        "coupés et injoignables (mesuré : jusqu'à 492 px hors écran sur "
        "/fundamentals)."
    )
    corps = regle.group(1)
    assert "overflow-x:auto" in corps.replace(" ", ""), (
        "Le tableau doit défiler horizontalement DANS lui-même — sinon "
        "`overflow-x:clip` sur body coupe ce qui dépasse sans laisser d'accès."
    )
    assert "display:block" in corps.replace(" ", ""), (
        "Sans `display:block`, un `<table>` ignore `overflow-x` : la règle "
        "serait inerte."
    )
    assert "min-width:100%" in corps.replace(" ", ""), (
        "Sans `min-width:100%`, un tableau étroit se rétracte à son contenu au lieu de "
        "remplir sa carte."
    )


def test_les_bulles_d_aide_ne_sortent_pas_de_l_ecran() -> None:
    """Une bulle de 240 px centrée sur son icône déborde dès que l'icône est à
    moins de 120 px du bord — le cas ordinaire en colonne de droite. Mesuré :
    99 px de texte coupés, donc illisibles. Sur mobile elle se pose en bas de
    l'écran, pleine largeur."""
    bloc = _bloc_mobile(CSS.read_text(encoding="utf-8"))
    regle = re.search(r'\[role="tooltip"\]\s*\{([^}]*)\}', bloc, re.S)
    assert regle, (
        "Plus de règle mobile pour [role=\"tooltip\"] : les bulles d'aide "
        "redeviennent coupées."
    )
    corps = regle.group(1).replace(" ", "")
    assert "position:fixed" in corps, "La bulle doit quitter l'ancrage sur son icône."
    assert "left:14px" in corps and "right:14px" in corps, (
        "La bulle doit occuper la largeur de l'écran."
    )


def test_les_marges_respectent_l_encoche_en_paysage() -> None:
    """En paysage sur un iPhone à encoche, une marge fixe de 14 px passe SOUS l'encoche.
    `max(14px, env(safe-area-inset-*))` garde le plus grand des deux — et ne coûte rien
    quand la marge de sécurité vaut zéro."""
    bloc = _bloc_mobile(CSS.read_text(encoding="utf-8")).replace(" ", "")
    for bord in ("left", "right"):
        assert f"padding-{bord}:max(14px,env(safe-area-inset-{bord}))" in bloc, (
            f"La marge {bord} de `main` ignore l'encoche : en paysage, le texte "
            f"passe dessous."
        )
