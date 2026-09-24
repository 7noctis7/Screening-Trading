"""« [Pièce jointe] Doge Long » sans l'image ne dit rien.

C'est le message réel qu'a affiché l'onglet à sa première ingestion : un signal réduit
à une mention de sa propre pièce jointe. Sur un compte de signaux, le graphique PORTE
souvent tout le contenu — l'écarter perd précisément ce qu'on vient chercher.

Ce que ces tests épinglent :
  1. les quatre sources relèvent les visuels, chacune à l'endroit qui lui est propre —
     Telegram en fond CSS, RSS en trois emplacements, Discord en pièces jointes et
     embeds, le JSONL par sa clé ;
  2. un message SANS TEXTE mais AVEC image n'est plus écarté ;
  3. seules les ADRESSES sont stockées : rien n'est téléchargé ni réhébergé ;
  4. le store survit à une base créée AVANT l'ajout de la colonne ;
  5. les doublons d'adresse sont retirés en gardant l'ordre de lecture.
"""
from __future__ import annotations

import io
import json
import sqlite3
from datetime import UTC, datetime

import pytest

from packages.social.modele import Publication
from packages.social.sources import charger_plugins, sources
from packages.social.store import StorePublications


@pytest.fixture(autouse=True)
def _plugins():
    charger_plugins()


def _brancher(monkeypatch, module, charge, json_=False):
    def faux(requete, timeout=None):  # noqa: ARG001
        brut = json.dumps(charge).encode() if json_ else charge.encode()
        rep = io.BytesIO(brut)
        rep.__enter__ = lambda: rep          # type: ignore[method-assign]
        rep.__exit__ = lambda *a: False      # type: ignore[method-assign]
        return rep
    monkeypatch.setattr(module.urllib.request, "urlopen", faux)


# ---- 1. chaque source, à son endroit --------------------------------------------

TG = """<html><body>
<div class="tgme_widget_message" data-post="c/1">
  <a class="tgme_widget_message_photo_wrap"
     style="background-image:url('https://cdn4.telesco.pe/file/a.jpg')"></a>
  <a class="tgme_widget_message_photo_wrap"
     style="background-image:url('https://cdn4.telesco.pe/file/a.jpg')"></a>
  <div class="tgme_widget_message_text">Doge Long, TP1 0.09</div>
  <a class="tgme_widget_message_date">
    <time datetime="2026-09-24T10:00:00+00:00"></time></a>
</div></body></html>"""


def test_telegram_lit_le_visuel_dans_le_FOND_CSS(monkeypatch):
    """Telegram ne met pas d'<img> : le visuel est un `background-image`."""
    import packages.social.sources.telegram as T
    _brancher(monkeypatch, T, TG)
    p = sources.create("telegram", canaux="c").lire()[0]
    assert p.images == ("https://cdn4.telesco.pe/file/a.jpg",)


def test_les_adresses_en_DOUBLE_sont_retirees_dans_l_ordre_de_lecture(monkeypatch):
    """La fixture cite deux fois la même image : elle ne doit apparaître qu'une fois."""
    import packages.social.sources.telegram as T
    _brancher(monkeypatch, T, TG)
    assert len(sources.create("telegram", canaux="c").lire()[0].images) == 1


RSS = """<?xml version="1.0"?><rss><channel><item>
<title>t</title><link>https://x.com/a/status/1</link>
<description>&lt;img src="https://pbs.twimg.com/media/z.jpg"&gt; BTC casse</description>
<enclosure url="https://exemple.test/e.png" type="image/png"/>
<pubDate>Wed, 24 Sep 2026 10:00:00 GMT</pubDate></item></channel></rss>"""


def test_rss_lit_l_enclosure_ET_l_img_de_la_description(monkeypatch):
    import packages.social.sources.rss as R
    _brancher(monkeypatch, R, RSS)
    p = sources.create("rss", flux="https://m.test/a/rss").lire()[0]
    assert p.images == ("https://exemple.test/e.png",
                        "https://pbs.twimg.com/media/z.jpg")


def test_discord_lit_les_pieces_jointes_ET_les_embeds(monkeypatch):
    import packages.social.sources.discord as D
    _brancher(monkeypatch, D, [{
        "id": "1", "content": "setup", "timestamp": "2026-09-24T10:00:00+00:00",
        "attachments": [{"url": "https://cdn.discordapp.com/a.png",
                         "content_type": "image/png"},
                        {"url": "https://cdn.discordapp.com/doc.pdf",
                         "content_type": "application/pdf"}],
        "embeds": [{"image": {"url": "https://cdn.discordapp.com/e.png"}}],
    }], json_=True)
    p = sources.create("discord", salons="1", jeton="x").lire()[0]
    assert p.images == ("https://cdn.discordapp.com/a.png",
                        "https://cdn.discordapp.com/e.png")
    assert "doc.pdf" not in " ".join(p.images)      # un PDF n'est pas un visuel


def test_le_jsonl_accepte_la_cle_images(tmp_path):
    f = tmp_path / "x.jsonl"
    f.write_text(json.dumps({
        "id": "1", "compte": "a", "ts": "2026-09-24T10:00:00Z", "texte": "ok",
        "images": ["https://x.test/1.jpg"]}) + "\n")
    p = sources.create("fichier", chemin=str(f)).lire()[0]
    assert p.images == ("https://x.test/1.jpg",)


# ---- 2. l'image seule est un message ---------------------------------------------

TG_SANS_TEXTE = """<html><body>
<div class="tgme_widget_message" data-post="c/2">
  <a class="tgme_widget_message_photo_wrap"
     style="background-image:url('https://cdn4.telesco.pe/file/graph.jpg')"></a>
  <a class="tgme_widget_message_date">
    <time datetime="2026-09-24T11:00:00+00:00"></time></a>
</div></body></html>"""


def test_un_message_SANS_TEXTE_mais_AVEC_image_n_est_plus_ecarte(monkeypatch):
    """Le graphique EST le message : l'écarter perdrait ce qu'on vient chercher."""
    import packages.social.sources.telegram as T
    _brancher(monkeypatch, T, TG_SANS_TEXTE)
    pubs = sources.create("telegram", canaux="c").lire()
    assert len(pubs) == 1
    assert pubs[0].images == ("https://cdn4.telesco.pe/file/graph.jpg",)
    assert "image(s) sans texte" in pubs[0].texte      # mention, pas invention


def test_un_message_sans_texte_NI_image_reste_ecarte(monkeypatch):
    import packages.social.sources.telegram as T
    _brancher(monkeypatch, T, """<div class="tgme_widget_message" data-post="c/3">
      <a class="tgme_widget_message_date">
        <time datetime="2026-09-24T11:00:00+00:00"></time></a></div>""")
    assert sources.create("telegram", canaux="c").lire() == []


# ---- 3. et 4. le stockage ---------------------------------------------------------

def test_seules_les_ADRESSES_sont_stockees_jamais_les_fichiers():
    """Rien n'est téléchargé ni réhébergé : le lecteur charge depuis la source.

    Réhéberger des visuels de tiers sur un site PUBLIC engagerait autre chose que de
    la technique — et ferait grossir un dépôt qui ne doit rien stocker de tel.
    """
    import re
    from pathlib import Path

    # `urlopen(` contient « open( » : la première version de ce garde-fou tombait sur
    # l'appel réseau légitime de chaque source. On ne vise que l'ouverture de FICHIER.
    ouvre_fichier = re.compile(r"(?<![A-Za-z_])open\(")
    for nom in ("telegram", "rss", "discord", "fichier"):
        code = Path(f"packages/social/sources/{nom}.py").read_text()
        if nom != "fichier":            # `fichier` lit un JSONL local, c'est son objet
            assert not ouvre_fichier.search(code), f"{nom} : un visuel serait recopié"
        for interdit in ("write_bytes", "urlretrieve", "b64encode"):
            assert interdit not in code, f"{nom} : {interdit} recopierait un visuel"


def test_le_store_survit_a_une_base_creee_AVANT_la_colonne(tmp_path):
    """`CREATE TABLE IF NOT EXISTS` ne touche pas une table existante : sans migration,
    la colonne manquerait et la panne surviendrait chez l'utilisateur, pas ici."""
    chemin = str(tmp_path / "x.db")
    c = sqlite3.connect(chemin)
    c.executescript("""CREATE TABLE publication (id TEXT PRIMARY KEY,
        compte TEXT NOT NULL, ts TEXT NOT NULL, texte TEXT NOT NULL,
        classification TEXT NOT NULL, ticker TEXT, symbole TEXT, direction TEXT,
        extraits TEXT NOT NULL, url TEXT);""")
    c.execute("INSERT INTO publication VALUES ('vieux','a',"
              "'2026-09-01T00:00:00+00:00','ancien','UNKNOWN',NULL,NULL,NULL,'{}',NULL)")
    c.commit()
    c.close()

    s = StorePublications(chemin)
    s.ecrire([Publication(id="neuf", compte="b", ts=datetime.now(UTC), texte="neuf",
                          images=("https://x.test/1.jpg",))])
    relues = {p.id: p for p in s.toutes()}
    s.close()
    assert relues["vieux"].images == ()          # l'ancien n'en avait pas
    assert relues["neuf"].images == ("https://x.test/1.jpg",)


def test_la_route_sert_les_images(tmp_path):
    from apps.api.social_x import construire_filtre, publications
    chemin = str(tmp_path / "x.db")
    s = StorePublications(chemin)
    s.ecrire([Publication(id="1", compte="a", ts=datetime.now(UTC), texte="t",
                          images=("https://x.test/1.jpg", "https://x.test/2.jpg"))])
    s.close()
    r = publications(construire_filtre(), db=chemin)
    servies = r["publications"][0]["images"]
    assert servies == ["https://x.test/1.jpg", "https://x.test/2.jpg"]
