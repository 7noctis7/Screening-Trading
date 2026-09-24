"""Deux moitiés écrites dans deux langages doivent se parler — et rien ne le vérifie.

Le navigateur écrit le JSONL, Python le lit. Aucun compilateur ne relie les deux : le
jour où l'un renomme un champ, l'export continue de produire un fichier d'apparence
normale et l'ingestion le rejette ligne par ligne. L'utilisateur voit « 0 nouvelle
publication » sans savoir pourquoi.

Ce test fait passer la sortie DÉCLARÉE du script d'export par le vrai ingesteur.

Il épingle en particulier l'horodatage : X rend `datetime="2026-09-24T10:00:00.000Z"`,
avec des millisecondes ET un `Z`. C'est le format le plus banal du web, et celui qui
fait tomber `fromisoformat` quand on ne l'a pas essayé.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import unquote

from packages.social.modele import Direction
from packages.social.sources import charger_plugins, sources

RACINE = Path(__file__).resolve().parents[2]
JS = RACINE / "tools" / "x_export.js"
JS_DISCORD = RACINE / "tools" / "discord_export.js"


def _champs_emis() -> set[str]:
    """Les clés que le script d'export écrit, lues dans le script lui-même."""
    code = JS.read_text(encoding="utf-8")
    bloc = code[code.index("return {"):code.index("};", code.index("return {"))]
    return set(re.findall(r"^\s*([a-z]+):", bloc, re.MULTILINE))


def test_le_script_emet_EXACTEMENT_ce_que_l_ingesteur_attend():
    """`compte` et `ts` sont obligatoires côté Python ; le reste est facultatif."""
    emis = _champs_emis()
    assert {"id", "compte", "ts", "texte"} <= emis, emis


def test_une_sortie_du_navigateur_est_ACCEPTEE_par_l_ingesteur(tmp_path):
    """Le format réel de X : millisecondes et suffixe Z."""
    ligne = {"id": "https://x.com/astekz/status/111", "compte": "astekz",
             "ts": "2026-09-24T10:00:00.000Z",
             "texte": "BTCUSDT long, entrée 64000 SL 61000",
             "url": "https://x.com/astekz/status/111"}
    f = tmp_path / "x.jsonl"
    f.write_text(json.dumps(ligne, ensure_ascii=False) + "\n")

    charger_plugins()
    src = sources.create("fichier", chemin=str(f))
    pubs = src.lire()

    assert src.rejets == [], src.rejets
    assert len(pubs) == 1
    p = pubs[0]
    assert p.compte == "astekz"
    assert p.ts.tzinfo is not None and p.ts.year == 2026
    assert (p.ticker, p.symbole) == ("BTC", "BTCUSDT")
    assert p.direction is Direction.LONG


def test_l_identifiant_est_le_LIEN_donc_reingerer_ne_duplique_pas(tmp_path):
    """Le script tire l'identifiant du lien canonique : deux exports se recouvrent."""
    code = JS.read_text(encoding="utf-8")
    assert "id: `https://x.com/${a[1]}/status/${a[2]}`" in code


def test_le_script_ne_FAIT_PAS_DEFILER_et_n_appelle_aucune_API():
    """Lire l'écran est un presse-papier ; parcourir X tout seul est un robot."""
    code = JS.read_text(encoding="utf-8")
    for interdit in ("scrollTo", "scrollBy", "setInterval", "setTimeout",
                     "fetch(", "XMLHttpRequest"):
        assert interdit not in code, f"{interdit} : ce script doit rester passif"


def test_un_selecteur_perime_AVERTIT_au_lieu_de_rendre_zero():
    """Zéro publication et « X a changé son balisage » ne doivent pas se ressembler."""
    code = JS.read_text(encoding="utf-8")
    assert "articles.length === 0" in code and "alert(" in code


def test_le_marque_page_est_le_script_LUI_MEME_pas_une_copie():
    """Une copie figée dans la doc diverge au premier correctif, sans qu'on le voie."""
    from scripts.x_bookmarklet import bookmarklet

    source = JS.read_text(encoding="utf-8")
    lien = bookmarklet(source)
    assert lien.startswith("javascript:")
    assert unquote(lien[len("javascript:"):]) == source


# ---- Discord : même contrat, mêmes refus -----------------------------------------

def test_l_export_discord_est_ACCEPTE_par_le_meme_ingesteur(tmp_path):
    """Un seul format d'entrée pour les deux exports — sinon deux chemins."""
    ligne = {"id": "discord:1234/5678", "compte": "eliz883",
             "ts": "2026-09-24T10:00:00.000Z",
             "texte": "BTCUSDT long, entrée 64000",
             "url": "https://discord.com/channels/@me/1234/5678"}
    f = tmp_path / "x.jsonl"
    f.write_text(json.dumps(ligne, ensure_ascii=False) + "\n")

    charger_plugins()
    src = sources.create("fichier", chemin=str(f))
    pubs = src.lire()
    assert src.rejets == [], src.rejets
    assert len(pubs) == 1 and pubs[0].compte == "eliz883"
    assert pubs[0].direction is Direction.LONG


def test_l_export_discord_ne_FAIT_PAS_DEFILER_et_n_appelle_aucune_API():
    """Le presse-papier reste un presse-papier : c'est ce qui le sépare d'un self-bot,
    la seule chose que Discord sanctionne par le bannissement."""
    code = JS_DISCORD.read_text(encoding="utf-8")
    for interdit in ("scrollTo", "scrollBy", "scrollIntoView", "setInterval",
                     "setTimeout", "fetch(", "XMLHttpRequest", "WebSocket",
                     "localStorage", "token"):
        assert interdit not in code, f"{interdit} : ce script doit rester passif"


def test_l_export_discord_AVERTIT_au_lieu_de_rendre_zero():
    code = JS_DISCORD.read_text(encoding="utf-8")
    assert "lignes.length === 0" in code and "alert(" in code


def test_l_identifiant_discord_porte_le_SALON_et_le_MESSAGE():
    """Le rang change au défilement ; l'identifiant de ligne, non."""
    code = JS_DISCORD.read_text(encoding="utf-8")
    assert "id: `discord:${m[1]}/${m[2]}`" in code


def test_les_DEUX_marque_pages_sont_leurs_scripts_eux_memes():
    from scripts.x_bookmarklet import SCRIPTS, bookmarklet

    for chemin in SCRIPTS.values():
        source = chemin.read_text(encoding="utf-8")
        assert unquote(bookmarklet(source)[len("javascript:"):]) == source, chemin
