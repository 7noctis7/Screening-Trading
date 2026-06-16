"""Vérifie les providers RÉELS + DuckDB dans TON environnement (réseau requis).

  uv pip install -e ".[data,api]" duckdb yfinance
  python scripts/verify_real_data.py

Teste : yfinance (OHLCV réel) → cache/fallback → stockage (sqlite ou duckdb) →
relecture, + FMP fondamental si FMP_API_KEY est défini. N'exécute aucun ordre.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.data import CachingProvider, FallbackProvider, data_providers  # noqa: E402
from packages.storage import make_bars_repository, validate_ohlcv, enforce  # noqa: E402


def check_ohlcv() -> bool:
    import pandas as pd
    yf = data_providers.create("yfinance")
    provider = CachingProvider(FallbackProvider([yf]))
    end = datetime.now(timezone.utc)
    bars = provider.fetch_ohlcv("AAPL", "1d", end - timedelta(days=120), end)
    if not bars:
        print("  ✗ yfinance : aucune barre (réseau/lib ?)"); return False
    df = pd.DataFrame([{"ts": b.ts, "open": b.open, "high": b.high, "low": b.low,
                        "close": b.close, "volume": b.volume} for b in bars]).set_index("ts")
    enforce(validate_ohlcv(df, "AAPL", "1d"))           # qualité bloquante
    backend = "duckdb" if _has("duckdb") else "sqlite"
    repo = make_bars_repository(backend, ":memory:")
    repo.upsert(bars, "silver")
    print(f"  ✓ yfinance {len(bars)} barres AAPL → qualité OK → {backend} {repo.count('silver')} lignes")
    return True


def check_fundamentals() -> bool:
    if not os.environ.get("FMP_API_KEY"):
        print("  ~ FMP : FMP_API_KEY absent → ignoré"); return True
    from packages.fundamentals import FMPFundamentalsProvider, ratios
    f = FMPFundamentalsProvider().get("AAPL")
    if f is None:
        print("  ✗ FMP : pas de données"); return False
    print(f"  ✓ FMP AAPL : ROE={ratios.roe(f):.1%} secteur={f.sector}")
    return True


def _has(mod: str) -> bool:
    try:
        __import__(mod); return True
    except ImportError:
        return False


def main() -> int:
    print("\n=== Vérification données réelles ===")
    ok = True
    try:
        ok &= check_ohlcv()
    except Exception as e:  # noqa: BLE001
        print(f"  ✗ OHLCV : {e}"); ok = False
    try:
        ok &= check_fundamentals()
    except Exception as e:  # noqa: BLE001
        print(f"  ✗ FMP : {e}"); ok = False
    print("=== " + ("OK" if ok else "ÉCHECS — voir ci-dessus") + " ===\n")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
