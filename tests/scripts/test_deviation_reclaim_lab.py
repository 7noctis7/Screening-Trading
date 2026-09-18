"""Le banc mesure-t-il ce qu'il prétend, et refuse-t-il de conclure sans données ?

CE QU'ON VÉRIFIE ICI, C'EST LA PLOMBERIE : que tous les scoreurs notent EXACTEMENT le
même échantillon (sinon l'écart mesuré mélange pouvoir prédictif et différence de
sélection, et ne veut plus rien dire), que le rendement est bien FORWARD avec entrée à
J+1, et que le banc dit UNCALIBRATED plutôt que d'inventer un verdict.

Le POUVOIR PRÉDICTIF, lui, ne se teste pas ici : il se mesure sur l'historique réel, et
sur lui seul. Un test qui « validerait » l'alpha sur des barres synthétiques validerait
le générateur de barres.
"""

from __future__ import annotations

import pathlib
import random
from dataclasses import dataclass

BANC = (pathlib.Path(__file__).resolve().parents[2] / "scripts"
        / "deviation_reclaim_lab.py").read_text(encoding="utf-8")


@dataclass
class B:
    high: float
    low: float
    close: float
    volume: float = 1e6
    ts: str = "2026-01-01"


def _serie(n: int = 320, graine: int = 11) -> list[B]:
    rng = random.Random(graine)
    px, out = 100.0, []
    for _ in range(n):
        px *= 1 + rng.gauss(0, 0.02)
        out.append(B(px * 1.02, px * 0.98, px))
    return out


def test_tous_les_scoreurs_notent_le_MEME_echantillon():
    """Le piège que `alpha_incremental` documente : comparer deux scoreurs sur des
    échantillons différents mélange leur pouvoir prédictif et leur sélection. Les
    longueurs doivent donc être égales — `comparer` lève une exception sinon."""
    from scripts.deviation_reclaim_lab import _collecter

    ev, sc = _collecter({"X": _serie(), "Y": _serie(graine=5)}, ["X", "Y"],
                        hold=5, pas=1, lag=1, depart=60)
    assert len(ev) > 100
    assert sc, "aucun scoreur"
    for nom, v in sc.items():
        assert len(v) == len(ev), f"{nom} : {len(v)} avis pour {len(ev)} événements"


def test_le_rendement_est_FORWARD_avec_entree_a_J_plus_1():
    """Entrer au close de la barre qui porte le signal suppose d'avoir vu, décidé et
    exécuté avant cette clôture — le look-ahead le plus banal."""
    from scripts.deviation_reclaim_lab import _rendement

    b = [B(1, 1, float(10 + k)) for k in range(20)]
    # signal à i=5 → entrée au close de 6 (16), sortie au close de 6+3=9 (19)
    assert _rendement(b, 5, hold=3, lag=1) == 19 / 16 - 1


def test_le_rendement_est_None_quand_l_avenir_manque():
    """Plutôt que zéro, qui se lirait « ce trade n'a rien rapporté »."""
    from scripts.deviation_reclaim_lab import _rendement

    b = [B(1, 1, 10.0) for _ in range(10)]
    assert _rendement(b, 8, hold=5, lag=1) is None


def test_la_primitive_EXISTANTE_est_dans_la_comparaison():
    """Toute la question est « le motif complet apporte-t-il quelque chose de plus que
    le SFP déjà codé le 02/09 ? ». Sans ce scoreur de référence, on mesure un signal
    dans le vide."""
    from scripts.deviation_reclaim_lab import _scores

    noms = set(_scores({"etat": "SEARCHING"}, [B(1, 1, 1)] * 3, 0))
    assert any("sfp_seul" in n for n in noms)
    assert {"deviation", "reclaim", "consolidation"} <= noms


def test_sans_base_reelle_le_banc_dit_UNCALIBRATED_et_ne_conclut_pas():
    """Un banc qui rend un verdict sur un univers synthétique est pire qu'un banc muet :
    il produit un chiffre que quelqu'un citera."""
    assert "UNCALIBRATED" in BANC
    assert "n_reels < 30" in BANC


def test_le_banc_applique_la_correction_de_TESTS_MULTIPLES():
    """Cinq scoreurs essayés, c'est cinq chances de tomber sur du bruit. `comparer`
    passe `n_essais` au DSR ; le banc doit l'utiliser, pas réimplémenter un placebo."""
    assert "from packages.research.alpha_incremental import" in BANC
    assert "comparer(" in BANC
    assert "tests multiples" in BANC


def test_le_banc_ne_pretend_RIEN_sur_le_4H():
    """La base est quotidienne. Une sortie qui mentionnerait un timeframe d'exécution
    4H afficherait un champ que rien ne soutient."""
    assert "QUOTIDIENNE" in BANC
    assert "UNCALIBRATED tant qu'aucune donnée intraday" in BANC
