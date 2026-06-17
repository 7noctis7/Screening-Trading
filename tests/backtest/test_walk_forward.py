from packages.backtest.walk_forward import walk_forward_splits


def test_anchored_train_grows():
    sp = walk_forward_splits(100, n_splits=5, train_frac=0.5, anchored=True)
    assert len(sp) >= 1
    assert all(tr.start == 0 for tr, _ in sp)            # ancré → train commence à 0
    assert all(te.start >= tr.stop for tr, te in sp)     # test après train (pas de fuite)


def test_rolling_window_fixed():
    sp = walk_forward_splits(120, n_splits=4, train_frac=0.5, anchored=False)
    sizes = {len(tr) for tr, _ in sp}
    assert all(te.start == tr.stop for tr, te in sp)
    assert len(sp) >= 1


def test_too_small():
    assert walk_forward_splits(3) == []
