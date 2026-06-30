"""Tests microstructure (OFI + vPIN) — purs, hors-ligne."""

from packages.research.microstructure import (
    bulk_buy_fraction,
    ofi_event,
    ofi_series,
    vpin,
)


def test_ofi_event_buy_pressure():
    # bid monte (nouvelle demande) + ask consommé → OFI nettement positif
    e = ofi_event(pb=100.5, qb=8, pa=101, qa=2, pb0=100.0, qb0=5, pa0=101, qa0=5)
    assert e > 0
    # bid baisse (annulations) + ask grossit → OFI négatif
    e2 = ofi_event(pb=99.5, qb=3, pa=100.5, qa=9, pb0=100.0, qb0=6, pa0=100.5, qa0=4)
    assert e2 < 0


def test_ofi_series_sums():
    book = [(100, 5, 101, 5), (100.5, 8, 101, 2), (101, 6, 101.5, 4)]
    assert ofi_series(book) == (
        ofi_event(100.5, 8, 101, 2, 100, 5, 101, 5)
        + ofi_event(101, 6, 101.5, 4, 100.5, 8, 101, 2))


def test_bulk_buy_fraction():
    assert bulk_buy_fraction(0.0, 1.0) == 0.5          # pas de mouvement → 50/50
    assert bulk_buy_fraction(2.0, 1.0) > 0.9           # forte hausse → achat
    assert bulk_buy_fraction(-2.0, 1.0) < 0.1          # forte baisse → vente
    assert bulk_buy_fraction(1.0, 0.0) == 0.5          # sigma nul → neutre


def test_vpin_one_sided_flow_is_toxic():
    # pas TOUS positifs mais variés (σ>0) → flux quasi 100% acheteur → vPIN haut
    up = [100.0]
    for i in range(80):
        up.append(up[-1] + (1.0 if i % 3 else 0.7))
    vols = [10.0] * len(up)
    out = vpin(up, vols, bucket=50, n_buckets=10)
    assert out["available"] and out["vpin"] > 0.7
    # flux équilibré (pas alternés +1/−1) → vPIN nettement plus bas
    bal = [100.0]
    for i in range(80):
        bal.append(bal[-1] + (1.0 if i % 2 == 0 else -1.0))
    out2 = vpin(bal, [10.0] * len(bal), bucket=50, n_buckets=10)
    assert out2["available"] and out2["vpin"] < out["vpin"]


def test_vpin_too_short():
    assert vpin([1, 2], [1, 1], bucket=10)["available"] is False
