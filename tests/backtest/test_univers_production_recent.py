"""L'univers de PRODUCTION doit se classer sur le momentum RÉCENT, pas sur 2015.

Constat du 26/08, sur données réelles. `make live` tourne en mode léger, qui coupe
la section `fundamentals` : `quality` est donc TOUJOURS vide en production et la
sélection part au repli momentum. Ce repli appelait `_price_universe`, qui mesure
le momentum au DÉBUT de la fenêtre commune — `s0 = max(lookback, 50) = 120` sur
2762 barres, soit le momentum de début 2015, puis figé.

Conséquence en chaîne, visible dans le diagnostic : l'indice `mkt` du panier périmé
affichait un drawdown supérieur à 15 %, la porte de RÉGIME mettait l'exposition
brute à zéro — pendant que la porte d'AMPLEUR voyait 100 % du même univers
au-dessus de sa MM200. Les deux portes décrivaient des marchés différents, ce qui
ne peut pas être vrai.

Le point de mesure au début est CORRECT pour le backtest (sans lui, on choisirait
l'univers avec de l'information future) et indéfendable en production, où
« aujourd'hui » EST le dernier point connu. Les deux premiers tests verrouillent
cette asymétrie.

PROTOCOLE. Deux familles au dessin opposé et sans hasard : l'une monte fort puis
s'effondre, l'autre stagne puis monte. Le classement de début de fenêtre doit
préférer la première, celui du dernier point la seconde. Aucun bruit : le
désaccord est structurel.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import numpy as np

from packages.backtest.preset_config import _price_universe, momentum_rank
from packages.backtest.preset_diag import Diag
from packages.backtest.preset_weights import (
    _selection,
    preset_latest_weights_explique,
)

N = 900
DEBUT = datetime(2021, 1, 1, tzinfo=UTC)


@dataclass
class Bar:
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


def _dates(n: int) -> list:
    out, d = [], DEBUT
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def _bars(px: np.ndarray) -> list:
    ds = _dates(len(px))
    return [Bar(ds[i], *(4 * [float(px[i])]), 1e6) for i in range(len(px))]


def _perime(decalage: float) -> np.ndarray:
    """Monte de 100 à 300 sur la première moitié, retombe à 150 sur la seconde."""
    h = N // 2
    return np.concatenate([np.linspace(100, 300 + decalage, h),
                           np.linspace(300 + decalage, 150, N - h)])


def _actuel(decalage: float) -> np.ndarray:
    """Plat sur la première moitié, monte de 100 à 260 sur la seconde."""
    h = N // 2
    return np.concatenate([np.full(h, 100.0),
                           np.linspace(100, 260 + decalage, N - h)])


def _panier() -> dict:
    """Les périmés sont nommés pour gagner TOUS les tris arbitraires.

    Premier écueil rencontré : baptisés VIEUX / ACTUEL, un repli sur l'ordre du
    dictionnaire retombait sur les bons titres par pur hasard alphabétique
    (`aligner_par_date` trie les noms), et le test passait sans rien mesurer.
    Ici « AAA » précède « ZZZ » et les périmés sont insérés en premier : seul un
    VRAI classement momentum peut retenir les titres forts aujourd'hui.
    """
    data = {}
    for i in range(8):
        data[f"AAAPERIME{i:02d}"] = _bars(_perime(i))
    for i in range(8):
        data[f"ZZZACTUEL{i:02d}"] = _bars(_actuel(i))
    return data


def test_la_production_choisit_les_titres_forts_AUJOURD_HUI():
    """Sans score qualité (mode léger), le repli doit classer sur le dernier point."""
    retenus = _selection(_panier(), {}, lookback=120, top_k=8, d=Diag())
    assert retenus is not None
    perimes = [s for s in retenus if s.startswith("AAAPERIME")]
    assert not perimes, f"titres effondrés retenus en production : {perimes}"


def test_le_backtest_classe_TOUJOURS_au_debut_de_la_fenetre():
    """Verrou anti-fuite : le défaut de `_price_universe` ne doit pas bouger.

    En backtest, classer au dernier point serait choisir l'univers en connaissant
    l'avenir. C'est le biais #2 que le dépôt a explicitement fermé.
    """
    data = _panier()
    retenus = _price_universe(data, list(data), lookback=120, top_k=8)
    assert all(s.startswith("AAAPERIME") for s in retenus), retenus


def test_le_repli_momentum_ne_degenere_pas_en_ordre_de_dictionnaire():
    """Le garde d'indice de `momentum_rank` doit accepter `s0 == len(série)`.

    Avec `len(M[s]) > s0`, aucun titre ne passait au dernier point : `sel` vide,
    `len(sel) < 5`, retour de `list(syms)[:top_k]` — l'ordre d'insertion. Le repli
    se serait dégradé en silence exactement en ce qu'il devait remplacer, et un test
    qui ne regarde que « la fonction renvoie 8 noms » l'aurait laissé passer.
    """
    M = {f"S{i}": np.linspace(100.0, 100.0 + i, 300) for i in range(10)}
    top = momentum_rank(M, list(M), s0=300, top_k=5)
    assert top == ["S9", "S8", "S7", "S6", "S5"], top
    assert top != list(M)[:5], "repli sur l'ordre du dictionnaire"


def test_la_porte_de_regime_nest_plus_annulee_par_un_panier_perime():
    """Le bout de chaîne : des poids non vides, et aucune porte à zéro."""
    poids, d = preset_latest_weights_explique(
        _panier(), quality={}, top_k=8, min_names=6, min_weight=0.0)
    assert d.gross.get("régime", 0.0) > 0.0, d.resume()
    assert poids, d.resume()


def test_le_diagnostic_chiffre_la_porte_de_regime():
    """Un multiplicateur seul ne dit pas s'il est LÉGITIME — il faut le drawdown.

    Trois hypothèses fausses ont été émises sur un `régime = 0.000` faute de cette
    ligne. Elle n'entre dans aucun calcul.
    """
    _poids, d = preset_latest_weights_explique(
        _panier(), quality={}, top_k=8, min_names=6, min_weight=0.0)
    detail = [x for e, x in d.etapes if e == "régime (détail)"]
    assert detail, d.resume()
    assert "DD" in detail[0] and "MM200" in detail[0], detail[0]
