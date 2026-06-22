import pytest

duckdb = pytest.importorskip("duckdb")   # skip si DuckDB absent (sandbox) — tourne en CI/local


def test_momentum_ranking_on_local_parquet(tmp_path):
    from packages.data.hf_cache import momentum_ranking
    pq = tmp_path / "market.parquet"
    # DuckDB écrit le parquet nativement (sans pyarrow) → fixture autoportante
    duckdb.sql(f"""
        COPY (
          SELECT * FROM (VALUES
            ('AAPL','2026-06-01',10.0),('AAPL','2026-06-20',12.0),
            ('NVDA','2026-06-01',10.0),('NVDA','2026-06-20', 9.0)
          ) t(symbol,date,close)
        ) TO '{pq}' (FORMAT PARQUET)""")
    out = momentum_ranking(days=60, limit=10, source=str(pq))
    assert out and out[0]["symbol"] == "AAPL"          # +20% > -10%
    assert out[0]["ret"] > out[-1]["ret"]
