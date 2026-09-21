"""Un fournisseur ne doit pas SERVIR ce qu'il n'a pas — et surtout pas l'étiqueter.

LE DÉFAUT (trouvé le 18/09 en cherchant comment ingérer du 1h/4h). `_TF_MAP` mappait
« 4h » sur « 1h », et `df_to_bars` étiquette les barres avec le timeframe DEMANDÉ :
`fetch_ohlcv(sym, "4h")` rendait donc des barres HORAIRES portant `timeframe="4h"`.

C'est le pire endroit possible pour un mensonge silencieux. Une barre mal étiquetée ne
provoque aucune erreur : elle se propage dans les indicateurs, les features et les
modèles, qui croient tous raisonner sur quatre heures. Et l'intention derrière le
mapping — « prends du 1h, tu agrégeras » — ne vaut rien tant que personne n'agrège.

Le fournisseur refuse désormais. L'agrégation reste la responsabilité de l'appelant ;
en crypto, Binance sert nativement le 4h (`packages/data/crypto_binance`).
"""

from __future__ import annotations

import pytest

from packages.data.providers.yfinance_provider import _TF_MAP, YFinanceProvider


def test_le_4h_n_est_plus_dans_la_table():
    assert "4h" not in _TF_MAP
    assert {"1d", "1h"} <= set(_TF_MAP), "les timeframes réellement servis restent"


def test_un_timeframe_NON_SERVI_leve_une_erreur_explicite():
    with pytest.raises(ValueError, match="ne sert pas"):
        YFinanceProvider().fetch_ohlcv("AAPL", "4h", "2026-01-01")


def test_le_message_ORIENTE_vers_la_solution():
    """Un refus qui ne dit pas quoi faire déplace le problème sans le résoudre."""
    with pytest.raises(ValueError) as e:
        YFinanceProvider().fetch_ohlcv("AAPL", "15m", "2026-01-01")
    texte = str(e.value)
    assert "Agréger" in texte and "Binance" in texte
    assert "'1d'" in texte or '"1d"' in texte, "les timeframes servis sont nommés"


def test_la_validation_precede_l_IMPORT_de_la_dependance():
    """Sur une machine sans yfinance, demander un timeframe non servi rendait un
    `ModuleNotFoundError` — un message qui parle d'autre chose que du vrai problème et
    envoie chercher au mauvais endroit."""
    with pytest.raises(ValueError):          # et NON ModuleNotFoundError
        YFinanceProvider().fetch_ohlcv("AAPL", "4h", "2026-01-01")
