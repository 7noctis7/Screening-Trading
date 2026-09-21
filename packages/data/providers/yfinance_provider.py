"""Provider yfinance (réel). Normalise en OHLCV UTC. Requiert `yfinance` + réseau.

La conversion DataFrame→Bar (`df_to_bars`) est PURE et testable hors-ligne en lui
injectant un DataFrame factice (pas besoin de yfinance pour tester la normalisation).
"""

from __future__ import annotations

from packages.core.models import Bar
from packages.data.registry import data_providers

# CE QUE YFINANCE SERT RÉELLEMENT. Le « 4h » n'y est pas : la table mappait donc
# `"4h" → "1h"` et rendait des barres HORAIRES portant `timeframe="4h"` (cf.
# `df_to_bars(df, symbol, timeframe)`, qui étiquette avec le timeframe DEMANDÉ). Le
# mensonge était silencieux, et c'est le pire endroit pour en avoir un : une barre mal
# étiquetée contamine tout ce qui la lit ensuite, indicateurs et modèles compris.
#
# Une intention correcte — « donne-moi du 4h, j'agrégerai » — ne rattrape rien tant que
# personne n'agrège. Le fournisseur refuse donc ce qu'il ne sert pas, et l'agrégation
# reste la responsabilité de l'appelant (cf. `deviation_reclaim.agreger_hebdo` pour le
# principe). En crypto, Binance sert nativement le 4h — `packages/data/crypto_binance`.
_TF_MAP = {"1d": "1d", "1h": "1h", "5m": "5m", "1m": "1m"}


def df_to_bars(df, symbol: str, timeframe: str) -> list[Bar]:
    """Convertit un DataFrame (index temporel, colonnes OHLCV) en barres UTC."""
    bars: list[Bar] = []
    for ts, row in df.iterrows():
        ts_utc = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
        bars.append(Bar(symbol, timeframe, ts_utc.to_pydatetime(),
                        float(row["Open"]), float(row["High"]), float(row["Low"]),
                        float(row["Close"]), float(row["Volume"])))
    return bars


@data_providers.register("yfinance")
class YFinanceProvider:
    name = "yfinance"

    def supports(self, symbol: str) -> bool:
        return True

    def fetch_ohlcv(self, symbol, timeframe, start, end=None) -> list[Bar]:
        # LA VALIDATION D'ABORD, l'import ENSUITE. Demander un timeframe non servi
        # sur une machine sans yfinance rendait un `ModuleNotFoundError` — un message
        # qui parle d'autre chose que du vrai problème, et envoie chercher au mauvais
        # endroit. Ce que l'appelant a mal demandé se dit avant toute dépendance.
        if timeframe not in _TF_MAP:
            raise ValueError(
                f"yfinance ne sert pas {timeframe!r} (servis : {sorted(_TF_MAP)}). "
                "Agréger depuis un timeframe servi, ou utiliser une source qui le "
                "sert nativement — Binance pour la crypto.")
        import yfinance as yf  # import local → core/tests restent sans dépendance
        interval = _TF_MAP[timeframe]
        df = yf.download(symbol, start=start, end=end, interval=interval,
                         auto_adjust=True, progress=False)
        if df is None or df.empty:
            return []
        if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
            df.columns = df.columns.get_level_values(0)  # aplatir multi-index
        return df_to_bars(df, symbol, timeframe)
