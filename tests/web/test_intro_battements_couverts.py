"""Chaque battement de l'intro doit avoir un ACTE et savoir dire son absence.

DÉFAUT DU 16/09. `SceneIntro.peindre` avait un `switch` écrit pour les QUATRE battements
d'origine — il citait encore une clé `resultat` supprimée depuis. Les sept battements
ajoutés (cinq fenêtres de performance + trades + révélation) tombaient tous dans `default`,
c'est-à-dire dans l'acte de RÉVÉLATION : un simple trait horizontal. Pendant les deux tiers
de l'intro, la toile ne peignait qu'une grille pâle.

Rien ne l'a signalé, et rien ne POUVAIT le signaler : un `switch` doté d'un `default` ne se
plaint jamais d'une clé qu'il ignore. TypeScript non plus, `b.cle` étant un `string`.
Ce test tient lieu d'exhaustivité.
"""

import pathlib
import re

INTRO = pathlib.Path(__file__).resolve().parents[2] / "apps" / "web" / "components" / "intro"


def _cles_des_beats() -> list[str]:
    src = (INTRO / "introConfig.ts").read_text(encoding="utf-8")
    bloc = src.split("export const BEATS = [", 1)[1].split("] as const;", 1)[0]
    return re.findall(r'\{\s*cle:\s*"([^"]+)"', bloc)


def _switch_de_la_scene() -> str:
    src = (INTRO / "introScene.ts").read_text(encoding="utf-8")
    return src.split("switch (b.cle) {", 1)[1].split("\n    }", 1)[0]


def test_les_neuf_battements_sont_declares():
    cles = _cles_des_beats()
    assert cles == ["echelle", "rejet", "p_ytd", "p_3a", "p_5a", "p_10a", "p_tout",
                    "trades", "reveal"]


def test_chaque_battement_est_cite_dans_le_switch():
    """Le fond du défaut : sept clés sur neuf n'étaient nommées nulle part."""
    sw = _switch_de_la_scene()
    manquants = [c for c in _cles_des_beats() if f'case "{c}"' not in sw]
    assert not manquants, (
        f"battements sans acte, ils tomberont dans `default` sans erreur : {manquants}")


def test_le_switch_ne_cite_aucune_cle_fantome():
    """`case \"resultat\"` a survécu des mois à la suppression de son battement."""
    sw = _switch_de_la_scene()
    cites = set(re.findall(r'case "([^"]+)"', sw))
    fantomes = sorted(cites - set(_cles_des_beats()))
    assert not fantomes, f"clés citées qui n'existent plus dans BEATS : {fantomes}"


def test_l_acte_mort_a_ete_retire_avec_ses_chiffres():
    """`beatResultat` n'était plus appelé mais portait encore « −9 % » / « −23 % » — les
    chiffres de l'ancienne landing, ceux-là mêmes qui mesuraient autre chose que ce
    qu'ils annonçaient (ADR-0154). Du code mort qui affirme est pire que du code mort."""
    actes = (INTRO / "introActs.ts").read_text(encoding="utf-8")
    assert "beatResultat" not in actes
    assert "−9 %" not in actes and "−23 %" not in actes


# ─── Une absence doit se DIRE ──────────────────────────────────────────────────────────

def test_une_periode_absente_affiche_son_motif():
    """Rendre `null` faisait disparaître le battement sans un mot : cinq secondes de noir
    indiscernables d'une panne, et on cherche le défaut dans le composant qui marche."""
    src = (INTRO / "IntroBeats.tsx").read_text(encoding="utf-8")
    assert "DONNÉE INDISPONIBLE" in src
    # Les deux genres qui dépendent de l'API doivent passer par `Absent`, pas par `null`.
    periode = src.split("const d = (data?.periodes || [])", 1)[1].split("return (", 1)[0]
    assert "<Absent" in periode and "return null" not in periode
    trades = src.split('if (b.genre === "trades")', 1)[1].split("return (", 1)[0]
    assert "<Absent" in trades and "return null" not in trades


def test_le_motif_distingue_donnee_absente_et_api_muette():
    """« pas de trades » et « l'API n'a pas répondu » demandent des gestes DIFFÉRENTS :
    le premier est normal sur un compte neuf, le second est une panne à corriger."""
    src = (INTRO / "IntroBeats.tsx").read_text(encoding="utf-8")
    assert "/api/intro n'a rien renvoyé" in src
    assert src.count("/api/intro n'a rien renvoyé") == 2   # période ET trades


def test_la_fenetre_est_nommee_meme_sans_donnee():
    """« donnée indisponible » sans dire DE QUOI ne vaut pas mieux que le silence."""
    src = (INTRO / "IntroBeats.tsx").read_text(encoding="utf-8")
    libelles = src.split("const LIBELLES", 1)[1].split("};", 1)[0]
    for cle in ("ytd", "3a", "5a", "10a", "tout"):
        assert f'"{cle}"' in libelles or f"{cle}:" in libelles
