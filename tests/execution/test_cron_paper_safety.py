from pathlib import Path


def test_cron_neutralise_toutes_les_cles_crypto_sans_rechargement_env():
    script = Path("scripts/cron_live.sh").read_text(encoding="utf-8")
    guard = script.split('if [ "${QUANT_NO_CRYPTO_LIVE:-1}" = "1" ]; then', 1)[1]
    guard = guard.split("fi", 1)[0]

    for key in (
        "BITMART_API_KEY",
        "BITMART_API_SECRET",
        "BITMART_API_MEMO",
        "BINANCE_API_KEY",
        "BINANCE_API_SECRET",
    ):
        assert f'{key}=""' in guard
    assert 'QUANT_BINANCE_TESTNET="1"' in guard
    assert "unset " not in guard
