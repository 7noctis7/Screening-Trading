"""Verrou de détention minimale — la sortie DURE passe toujours, les MOLLES attendent.

Hypothèse de l'utilisateur (04/09) : les trades tenus moins de 10 jours perdent, donc
imposer un plancher de détention laisserait le trade « nettoyer » sa volatilité.
Le journal ne pouvait pas trancher (les longues détentions y sont toutes des tranches
crypto d'un même lot, sur un rallye) — d'où le paramètre à balayer dans `sortie_lab`.
Ici on valide la MÉCANIQUE du verrou, pas la stratégie.
"""
from packages.backtest.fast_swing import _sortie


class _Bar:
    def __init__(self, low: float, high: float, close: float) -> None:
        self.low, self.high, self.close = low, high, close


def _lot(stop: float = 90.0, target: float = 130.0, hh: float = 100.0) -> dict:
    return {"stop": stop, "target": target, "hh": hh, "entry_price": 100.0}


def test_stop_initial_passe_meme_verrouille():
    """Le garde-fou ne se désactive JAMAIS : sinon le maxDD changerait de sens."""
    px, motif = _sortie(_Bar(low=89.0, high=101.0, close=89.5), _lot(),
                        atr_t=2.0, sma_longue=95.0, trail_atr=5.0, verrouille=True)
    assert px == 90.0 and motif == "stop_hit"


def test_cible_atteinte_est_differee_par_le_verrou():
    bar = _Bar(low=99.0, high=131.0, close=130.5)
    assert _sortie(bar, _lot(), atr_t=2.0, sma_longue=95.0, trail_atr=0.0,
                   verrouille=True) == (None, None)
    px, motif = _sortie(bar, _lot(), atr_t=2.0, sma_longue=95.0, trail_atr=0.0,
                        verrouille=False)
    assert px == 130.0 and motif == "target_hit"


def test_stop_suiveur_est_differe_par_le_verrou():
    """Suiveur à 5 ATR sous un plus haut de 120 → 110 ; la barre y touche."""
    bar, lot = _Bar(low=109.0, high=118.0, close=110.0), _lot(hh=120.0)
    assert _sortie(bar, lot, atr_t=2.0, sma_longue=95.0, trail_atr=5.0,
                   verrouille=True) == (None, None)
    px, motif = _sortie(bar, lot, atr_t=2.0, sma_longue=95.0, trail_atr=5.0,
                        verrouille=False)
    assert px == 110.0 and motif == "trailing_stop"


def test_cassure_de_tendance_est_differee_par_le_verrou():
    bar = _Bar(low=94.0, high=99.0, close=94.5)
    assert _sortie(bar, _lot(), atr_t=2.0, sma_longue=96.0, trail_atr=0.0,
                   verrouille=True) == (None, None)
    px, motif = _sortie(bar, _lot(), atr_t=2.0, sma_longue=96.0, trail_atr=0.0,
                        verrouille=False)
    assert px == 94.5 and motif == "cassure tendance (MM longue)"


def test_sans_verrou_le_comportement_est_inchange():
    """Barre neutre : aucune sortie, verrou ou pas — le verrou n'invente rien."""
    bar = _Bar(low=99.0, high=101.0, close=100.0)
    for v in (True, False):
        assert _sortie(bar, _lot(), atr_t=2.0, sma_longue=95.0, trail_atr=5.0,
                       verrouille=v) == (None, None)


def test_le_stop_prime_sur_la_cible_dans_la_meme_barre():
    """Barre qui touche les deux : on retient le stop — hypothèse conservatrice."""
    px, motif = _sortie(_Bar(low=89.0, high=131.0, close=100.0), _lot(),
                        atr_t=2.0, sma_longue=95.0, trail_atr=0.0, verrouille=False)
    assert px == 90.0 and motif == "stop_hit"
