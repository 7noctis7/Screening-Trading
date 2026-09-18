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


def test_le_banc_DIT_sur_quel_timeframe_chaque_niveau_est_lu():
    """La spec place la résistance de confirmation sur l'exécution (4H). Le 4H n'existe
    pas ici : elle est lue sur le PRINCIPAL. Une sortie muette là-dessus laisserait
    supposer le 4H — et un niveau dont on croit connaître l'origine est pire qu'un
    niveau absent."""
    actions = BANC.split("def _timeframes")[1].split("\ndef ")[0].split("else:")[1]
    assert "1D" in actions and "PAS en 4H" in actions
    assert "UNCALIBRATED" in actions
    assert "QUOTIDIENNE" in BANC


def test_le_WEEKLY_est_derive_du_daily_et_porte_la_cible_macro():
    """Le Weekly s'agrège exactement depuis le Daily — aucune source nouvelle. Le 4H,
    lui, ne se déduit de rien : il faudrait l'ingérer."""
    assert "agreger_hebdo" in BANC
    assert "hebdo=hebdo" in BANC


# ─── La source crypto intraday (18/09) ─────────────────────────────────────────────

def test_le_banc_sait_lire_la_base_CRYPTO_intraday():
    """C'est le seul endroit où le timeframe d'exécution de la spec existe vraiment."""
    assert "--source" in BANC and '"crypto"' in BANC
    assert "crypto_intraday.db" in BANC
    assert "_donnees_crypto" in BANC


def test_sans_base_intraday_le_banc_DIT_quoi_lancer():
    """« UNCALIBRATED » sans la marche à suivre laisse l'utilisateur devant un mur."""
    assert "make ingest-crypto-intraday" in BANC


def test_le_pied_de_page_SUIT_la_source_et_ne_la_decrit_pas_de_memoire():
    """LE défaut que ce test ferme. Le pied de page annonçait « Principal : 1D · aucune
    donnée intraday n'existe dans ce dépôt » quelle que soit la source — vrai sur
    actions, FAUX dès la première mesure crypto en 1h. Un rapport qui décrit autre chose
    que ce qu'il vient de calculer est la pire espèce d'erreur : rien ne cloche à
    l'écran."""
    bloc = BANC.split("def _timeframes")[1].split("\ndef ")[0]
    assert 'a.source == "crypto"' in bloc, "le pied de page doit brancher sur la source"
    assert "{a.tf}" in bloc, "il doit nommer le timeframe RÉELLEMENT utilisé"
    assert "UNCALIBRATED" in bloc, "et rappeler ce qui reste non mesuré côté actions"


def test_hold_se_compte_en_BARRES_et_le_dit():
    """Cinq barres valent cinq jours en quotidien et cinq heures en 1h. L'afficher en
    « j » ferait comparer deux horizons sous le même nom."""
    assert "horizon {hold} barres" in BANC
    assert "hold` se compte en BARRES" in BANC


# ── Le gate lui-même : ce qui a failli faire câbler du bruit (18/09) ──────────

def test_le_TEMOIN_toujours_long_est_note_comme_les_autres():
    """Sans étalon, un Sharpe positif se lit comme une découverte alors qu'il peut
    n'être que la dérive du marché. Le témoin note TOUTES les barres, donc il capte
    exactement cette dérive — et tout scoreur qui ne le bat pas ne vaut rien."""
    from scripts.deviation_reclaim_lab import TEMOIN, _collecter

    ev, sc = _collecter({"X": _serie()}, ["X"], hold=5, pas=1, lag=1, depart=60)
    assert TEMOIN in sc, "le témoin a disparu des scoreurs"
    assert set(sc[TEMOIN]) == {1.0}, "le témoin doit être allumé sur CHAQUE barre"
    assert len(sc[TEMOIN]) == len(ev)


def test_le_n_EFFECTIF_divise_par_l_horizon_et_par_les_dates_repetees():
    """200 titres notés le même jour subissent la même séance : ce n'est pas 200
    mesures. Et un rendement forward recalculé à chaque barre se recouvre."""
    from packages.research.alpha_incremental import Evenement
    from scripts.deviation_reclaim_lab import _n_effectif

    ev = [Evenement(s, f"2026-01-{j:02d}", "E", 0.0)
          for j in range(1, 21) for s in ("A", "B", "C")]   # 60 obs, 20 dates
    assert len(ev) == 60
    assert _n_effectif(ev, hold=5) == 4        # 20 dates / 5 barres d'horizon
    assert _n_effectif(ev, hold=1) == 20       # jamais plus que les dates
    assert _n_effectif(ev, hold=999) == 2      # plancher : on ne descend pas sous 2


def test_le_DSR_ne_vaut_plus_1_000_sur_du_BRUIT_quand_le_n_est_EFFECTIF():
    """LE DÉFAUT QUI A FAILLI PASSER. Le DSR divise par √n : à n = 499 585 il vaut
    1,000 pour n'importe quel Sharpe positif, y compris celui d'un scoreur TIRÉ AU
    HASARD sur des rendements sans aucun signal. Le garde-fou ne gardait plus rien."""
    import random as _r

    from packages.research.alpha_incremental import Evenement, evaluer

    rng = _r.Random(0)
    n = 40_000
    ev = [Evenement("X", f"j{k // 200}", "E", rng.gauss(0.004, 0.08)) for k in range(n)]
    hasard = [float(rng.random() < 0.4) for _ in range(n)]

    brut = evaluer("hasard", ev, hasard, hold=10, n_essais=5)
    effectif = evaluer("hasard", ev, hasard, hold=10, n_essais=5, n_effectif=20)
    assert abs(brut.ic) < 0.02, "aucun signal n'existe par construction"
    assert brut.dsr > effectif.dsr, (
        f"le n effectif doit DURCIR le garde-fou : {brut.dsr} vs {effectif.dsr}")


def test_un_IC_NEGATIF_ne_peut_pas_etre_RETENU():
    """`placebo` teste |IC| : il est BILATÉRAL. Des barres qui sous-performent
    significativement le passent aussi bien que des barres qui prédisent. Ces
    scoreurs sont LONGS — un IC négatif dit d'ÉVITER ces barres, pas de les acheter.
    Le banc les affichait « RETENU »."""
    from scripts.deviation_reclaim_lab import _verdict

    def _m(ic):
        return {"n": 5000, "ic": ic, "sharpe": 0.2, "dsr": 1.0, "p_placebo": 0.002,
                "part_notee": 0.4, "rendement_moyen": 0.0}

    res = {"mesures": {"sous-performe": _m(-0.09), "predit": _m(+0.09)},
           "n_evenements": 5000, "n_essais": 2}
    assert _verdict(res) == ["predit"]


def test_la_PRIME_de_selection_ne_punit_pas_un_scoreur_RARE(capsys):
    """LE DÉFAUT DE LECTURE DU 18/09. La colonne « Sharpe » note une stratégie qui reste
    à ZÉRO hors signal : elle vaut donc ~√(part allumée) × le Sharpe des barres
    retenues. Un scoreur allumé 1 % du temps y est écrasé sans avoir démérité, et le
    témoin « toujours long » le bat avec un t énorme qui ne mesure que le taux
    d'investissement. La prime compare ce qui est comparable : barres retenues contre
    toutes les barres."""
    from packages.research.alpha_incremental import Evenement
    from scripts.deviation_reclaim_lab import _prime_selection

    rng = random.Random(3)
    n = 1000
    # 10 % des barres portent une forte prime, les autres du bruit centré. Le bruit
    # n'est pas décoratif : une série ALLUMÉE sans dispersion rend un t indéfini, et
    # c'est le piège `_degenere` que `alpha_incremental` documente déjà.
    rends = [(0.05 if k % 10 == 0 else 0.0) + rng.gauss(0, 0.01) for k in range(n)]
    ev = [Evenement("X", f"j{k}", "E", r) for k, r in enumerate(rends)]
    scores = {"juste": [1.0 if k % 10 == 0 else 0.0 for k in range(n)],
              "faux": [1.0 if k % 10 == 1 else 0.0 for k in range(n)]}

    _prime_selection(ev, scores, n_effectif=n)
    lignes = capsys.readouterr().out.splitlines()
    juste = next(x for x in lignes if x.startswith("    juste"))
    faux = next(x for x in lignes if x.startswith("    faux"))
    assert float(juste.split()[-2]) > 0.04, f"prime franchement positive : {juste}"
    assert float(faux.split()[-2]) < 0, f"prime négative attendue : {faux}"
    assert float(juste.split()[-1]) > 2, "une sélection utile doit sortir du bruit"
    assert float(faux.split()[-1]) < 0, "une sélection nuisible doit se voir aussi"
