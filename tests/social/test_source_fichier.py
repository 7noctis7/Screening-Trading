"""Une ligne illisible qu'on devine est pire qu'une ligne illisible qu'on jette.

Deviner, c'est fabriquer une publication que personne n'a écrite — et elle sera
indiscernable des vraies dans l'onglet. Le rejet, lui, se compte et se rapporte.

Ce que ces tests épinglent :
  1. une donnée LUE bat toujours une donnée DÉDUITE ;
  2. une ligne cassée est comptée dans `rejets`, pas devinée ni tue ;
  3. une publication sans horodatage est refusée — elle ne se trierait pas ;
  4. le « @ » du compte est retiré, sinon « @astekz » et « astekz » feraient deux
     comptes distincts ;
  5. un fichier absent rend `[]`, pas une erreur : le flux est simplement non branché.
"""
from __future__ import annotations

import json

from packages.social.modele import Classification, Direction
from packages.social.sources import charger_plugins, sources


def _ecrire(tmp_path, lignes: list) -> str:
    f = tmp_path / "x.jsonl"
    f.write_text("\n".join(json.dumps(x, ensure_ascii=False) if isinstance(x, dict)
                           else str(x) for x in lignes))
    return str(f)


def _source(chemin: str):
    charger_plugins()
    return sources.create("fichier", chemin=chemin)


def test_une_etiquette_LUE_bat_une_etiquette_DEDUITE(tmp_path):
    """Le texte dit « rappel » (EDUCATIONAL), la source dit NEWS. La source gagne."""
    c = _ecrire(tmp_path, [{"id": "1", "compte": "a", "ts": "2026-09-24T10:00:00Z",
                            "texte": "Rappel sur les volumes",
                            "classification": "NEWS"}])
    assert _source(c).lire()[0].classification is Classification.NEWS


def test_sans_etiquette_l_extraction_pre_remplit(tmp_path):
    c = _ecrire(tmp_path, [{"id": "1", "compte": "a", "ts": "2026-09-24T10:00:00Z",
                            "texte": "achat BTCUSDT, entrée 64000"}])
    p = _source(c).lire()[0]
    assert (p.ticker, p.symbole) == ("BTC", "BTCUSDT")
    assert p.direction is Direction.LONG
    assert p.classification is Classification.TRADE_SIGNAL


def test_une_ligne_CASSEE_est_comptee_et_non_devinee(tmp_path):
    c = _ecrire(tmp_path, [{"id": "1", "compte": "a", "ts": "2026-09-24T10:00:00Z",
                            "texte": "ok"}, "{ pas du json"])
    src = _source(c)
    assert len(src.lire()) == 1
    assert len(src.rejets) == 1 and "ligne 2" in src.rejets[0]


def test_une_publication_SANS_horodatage_est_refusee(tmp_path):
    """Sans date elle ne se trie pas — la ranger « quelque part » serait un mensonge."""
    c = _ecrire(tmp_path, [{"id": "1", "compte": "a", "texte": "ok"}])
    src = _source(c)
    assert src.lire() == []
    assert len(src.rejets) == 1


def test_le_arobase_du_compte_est_retire(tmp_path):
    """« @astekz » et « astekz » doivent être UN compte, pas deux dans le filtre."""
    c = _ecrire(tmp_path, [{"id": "1", "compte": "@astekz",
                            "ts": "2026-09-24T10:00:00Z", "texte": "ok"}])
    assert _source(c).lire()[0].compte == "astekz"


def test_un_fichier_ABSENT_rend_une_liste_vide_pas_une_erreur(tmp_path):
    """Le flux n'est pas branché — ce n'est pas une panne, et ça se dit à l'écran."""
    assert _source(str(tmp_path / "rien.jsonl")).lire() == []


def test_un_horodatage_SANS_fuseau_est_lu_en_UTC(tmp_path):
    c = _ecrire(tmp_path, [{"id": "1", "compte": "a", "ts": "2026-09-24T10:00:00",
                            "texte": "ok"}])
    assert _source(c).lire()[0].ts.tzinfo is not None
