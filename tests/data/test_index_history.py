from datetime import UTC, datetime

from packages.core.models import Bar
from packages.data.index_history import choose_history, merge_bars


def _bars(symbol: str, dates: list[str], base: float = 100.0):
    return [
        Bar(
            symbol,
            "1d",
            datetime.fromisoformat(d).replace(tzinfo=UTC),
            base + i,
            base + i,
            base + i,
            base + i,
            1_000,
        )
        for i, d in enumerate(dates)
    ]


def test_serie_fraiche_prime_sur_serie_plus_longue_mais_perimee():
    histories = {"^GSPC": {}, "SPY": {}}
    stale = [f"2026-06-{d:02d}" for d in range(1, 29)]
    fresh = [f"2026-08-{d:02d}" for d in range(1, 29)]
    merge_bars(histories["^GSPC"], _bars("^GSPC", stale))
    merge_bars(histories["SPY"], _bars("SPY", fresh))
    out = choose_history(["^GSPC", "SPY"], histories, "2026-08-29", min_bars=20)
    assert out and out.alias == "SPY" and out.fresh


def test_meme_alias_est_fusionne_par_date_sans_plateau_artificiel():
    history = {}
    merge_bars(history, _bars("^NDX", ["2026-08-25", "2026-08-26"], 100))
    merge_bars(history, _bars("^NDX", ["2026-08-27", "2026-08-28"], 102))
    out = choose_history(["^NDX"], {"^NDX": history}, "2026-08-29", min_bars=2)
    assert out and out.dates[-1] == "2026-08-28"
    assert len(out.closes) == 4 and len(set(out.closes)) == 4


def test_serie_perimee_est_signalee_non_fraiche():
    history = {}
    dates = [f"2026-06-{d:02d}" for d in range(1, 29)]
    merge_bars(history, _bars("^GSPC", dates))
    out = choose_history(["^GSPC"], {"^GSPC": history}, "2026-08-29", min_bars=20)
    assert out and out.fresh is False
