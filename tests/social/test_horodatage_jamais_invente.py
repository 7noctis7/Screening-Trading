"""Une date inventée place le message à l'endroit le plus lu de l'écran.

C'est ce qui rend ce défaut vicieux. `datetime.now()` en secours paraît prudent — il
évite un plantage — mais il date le message de MAINTENANT : il passe donc en tête de
liste, là où l'œil va en premier. Et comme le store écrit en `INSERT OR REPLACE`, la
fausse date se rafraîchit à chaque ingestion : un vieux billet devient éternellement la
dernière nouvelle. Refuser l'élément est moins grave que le mettre en avant.

Le premier test épingle un défaut RÉEL, trouvé par la revue : l'analyseur Telegram
clôturait l'enregistrement à la fermeture du bloc TEXTE, alors que `<time>` est un frère
qui vient APRÈS, dans le pied du message. Toutes les publications partaient sans date —
et mes huit tests d'alors vérifiaient le texte, le compte et l'identifiant, jamais la
date. Un test qui n'interroge pas le champ fautif ne protège de rien.
"""
from __future__ import annotations

import io
import json
from datetime import UTC, datetime

import pytest

from packages.social.sources import charger_plugins, sources

TG = """<html><body>
<div class="tgme_widget_message_wrap"><div class="tgme_widget_message"
     data-post="c/1">
  <div class="tgme_widget_message_text">BTC tient bien</div>
  <div class="tgme_widget_message_footer"><div class="tgme_widget_message_info">
    <a class="tgme_widget_message_date" href="https://t.me/c/1">
      <time datetime="2026-09-20T08:30:00+00:00" class="time">08:30</time></a>
  </div></div>
</div></div>
<div class="tgme_widget_message_wrap"><div class="tgme_widget_message"
     data-post="c/2">
  <div class="tgme_widget_message_text">message sans date</div>
</div></div>
</body></html>"""

RSS_SANS_DATE = """<?xml version="1.0"?><rss><channel>
<item><title>t</title><link>https://x.com/a/status/1</link>
<description>BTC</description></item>
<item><title>u</title><link>https://x.com/a/status/2</link>
<description>ETH</description><pubDate>Wed, 24 Sep 2026 10:00:00 GMT</pubDate></item>
</channel></rss>"""


@pytest.fixture(autouse=True)
def _plugins():
    charger_plugins()


def _brancher(monkeypatch, module, charge, json_=False):
    def faux(requete, timeout=None):  # noqa: ARG001
        if isinstance(charge, Exception):
            raise charge
        brut = json.dumps(charge).encode() if json_ else charge.encode()
        rep = io.BytesIO(brut)
        rep.__enter__ = lambda: rep          # type: ignore[method-assign]
        rep.__exit__ = lambda *a: False      # type: ignore[method-assign]
        return rep

    monkeypatch.setattr(module.urllib.request, "urlopen", faux)


def test_REGRESSION_telegram_lit_bien_le_time_du_PIED_de_message(monkeypatch):
    """`<time>` est un FRÈRE placé APRÈS le bloc texte, pas un descendant."""
    import packages.social.sources.telegram as T
    _brancher(monkeypatch, T, TG)
    pubs = sources.create("telegram", canaux="c").lire()
    assert len(pubs) == 1
    assert pubs[0].ts == datetime(2026, 9, 20, 8, 30, tzinfo=UTC)


def test_telegram_ECARTE_le_message_sans_date_et_le_DIT(monkeypatch):
    import packages.social.sources.telegram as T
    _brancher(monkeypatch, T, TG)
    src = sources.create("telegram", canaux="c")
    src.lire()
    assert any("écarté" in r and "date" in r for r in src.rejets), src.rejets


def test_rss_ECARTE_l_element_sans_pubDate_et_le_DIT(monkeypatch):
    import packages.social.sources.rss as R
    _brancher(monkeypatch, R, RSS_SANS_DATE)
    src = sources.create("rss", flux="https://m.test/a/rss")
    pubs = src.lire()
    assert len(pubs) == 1 and pubs[0].texte == "ETH"
    assert any("écarté" in r for r in src.rejets), src.rejets


def test_discord_ECARTE_le_message_sans_horodatage_et_le_DIT(monkeypatch):
    import packages.social.sources.discord as D
    _brancher(monkeypatch, D, [
        {"id": "1", "content": "BTC", "timestamp": "pas une date"},
        {"id": "2", "content": "ETH", "timestamp": "2026-09-24T10:00:00+00:00"},
    ], json_=True)
    src = sources.create("discord", salons="1", jeton="x")
    pubs = src.lire()
    assert len(pubs) == 1 and pubs[0].texte == "ETH"
    assert any("écarté" in r for r in src.rejets), src.rejets


def test_AUCUNE_source_ne_se_rabat_sur_l_heure_courante():
    """Le garde-fou sur le CODE : `datetime.now` n'a rien à faire dans un horodatage."""
    from pathlib import Path
    for nom in ("telegram", "rss", "discord"):
        code = Path(f"packages/social/sources/{nom}.py").read_text()
        corps = code[code.index("def _quand"):]
        corps = corps[:corps.index("def ", 10)] if "def " in corps[10:] else corps
        lignes = [x for x in corps.splitlines() if not x.strip().startswith("#")]
        actif = "\n".join(lignes).split('"""')
        actif = "".join(actif[::2])          # hors docstring
        assert "now(" not in actif, f"{nom} : une date inventée est revenue"
