"""« Ne garder que les 50 plus récents à chaque fois » — PAR COMPTE, et dans le temps.

Ce que ces tests épinglent :
  1. le plafond est PAR COMPTE : un plafond global laisserait le compte le plus bavard
     évincer les autres — trendspider publie bien plus qu'astekz ;
  2. « plus récent » se juge sur des DATES, pas sur du texte ISO : deux fuseaux
     différents trient faux dans l'ordre alphabétique ;
  3. `0` ne supprime rien ;
  4. un message plus ancien que le plafond, relu à chaque passage, n'est PAS annoncé
     comme « nouveau » à chaque passage.
"""
from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

from packages.social.modele import Publication
from packages.social.store import StorePublications

RACINE = Path(__file__).resolve().parents[2]
T0 = datetime(2026, 9, 24, 12, tzinfo=UTC)


def _pubs(compte: str, n: int, *, depuis: datetime = T0) -> list[Publication]:
    return [Publication(id=f"{compte}-{k}", compte=compte, texte=f"message {k}",
                        ts=depuis - timedelta(hours=k)) for k in range(n)]


def test_le_plafond_est_PAR_COMPTE():
    s = StorePublications()
    s.ecrire(_pubs("trendspider", 80) + _pubs("astekz", 5))
    assert s.garder_recentes(50) == 30
    restes = [p.compte for p in s.toutes()]
    assert restes.count("trendspider") == 50
    assert restes.count("astekz") == 5, "le compte discret a été évincé par le bavard"


def test_ce_sont_les_PLUS_RECENTES_qui_restent():
    s = StorePublications()
    s.ecrire(_pubs("astekz", 60))
    s.garder_recentes(50)
    assert s.ids() == {f"astekz-{k}" for k in range(50)}   # k=0 est le plus récent


def test_la_recence_se_juge_sur_des_DATES_pas_sur_du_texte():
    """« 10:30+02:00 » (= 08:30 UTC) est PLUS ANCIEN que « 09:00+00:00 », mais passe
    DEVANT dans l'ordre alphabétique."""
    paris = timezone(timedelta(hours=2))
    s = StorePublications()
    s.ecrire([Publication(id="ancien", compte="a", texte="x",
                          ts=datetime(2026, 9, 24, 10, 30, tzinfo=paris)),
              Publication(id="recent", compte="a", texte="y",
                          ts=datetime(2026, 9, 24, 9, 0, tzinfo=UTC))])
    s.garder_recentes(1)
    assert s.ids() == {"recent"}


def test_zero_ne_supprime_RIEN():
    s = StorePublications()
    s.ecrire(_pubs("astekz", 70))
    assert s.garder_recentes(0) == 0 and s.compter() == 70


def _ingerer(tmp_path: Path, jsonl: Path, garder: int) -> str:
    r = subprocess.run(
        [sys.executable, "scripts/social_x_ingest.py", "--source", "fichier",
         "--chemin", str(jsonl), "--db", str(tmp_path / "s.db"),
         "--garder", str(garder)],
        cwd=RACINE, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_un_message_trop_ancien_n_est_pas_NOUVEAU_a_chaque_passage(tmp_path):
    """Relu à chaque passage puis retiré aussitôt : il ne doit jamais compter."""
    import json
    lignes = [{"id": str(k), "compte": "astekz", "texte": f"m{k}",
               "ts": (T0 - timedelta(hours=k)).isoformat()} for k in range(3)]
    jsonl = tmp_path / "x.jsonl"
    jsonl.write_text("\n".join(json.dumps(x) for x in lignes))
    premier = _ingerer(tmp_path, jsonl, garder=2)
    assert "Nouvelles : 2" in premier and "Retirées  : 1" in premier
    second = _ingerer(tmp_path, jsonl, garder=2)
    assert "Nouvelles : 0" in second, second
    assert "Stock     : 2" in second
