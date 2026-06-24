"""Tests du ledger d'hypothèses d'alpha."""

from packages.research.ledger import (
    append_record,
    best_by_dsr,
    read_records,
    summary,
    trial_count,
)


def test_append_and_read(tmp_path):
    p = tmp_path / "h.jsonl"
    append_record({"facteur": "momentum", "dsr": 0.01, "classe": ["equity"]}, p)
    append_record({"facteur": "trend", "dsr": 0.6, "classe": ["crypto"]}, p)
    recs = read_records(p)
    assert len(recs) == 2 and recs[0]["facteur"] == "momentum"


def test_read_missing_file_is_empty(tmp_path):
    assert read_records(tmp_path / "none.jsonl") == []


def test_read_skips_corrupt_lines(tmp_path):
    p = tmp_path / "h.jsonl"
    p.write_text('{"facteur": "x", "dsr": 0.2}\nNOT JSON\n\n', encoding="utf-8")
    assert len(read_records(p)) == 1


def test_trial_count_filters(tmp_path):
    p = tmp_path / "h.jsonl"
    append_record({"facteur": "momentum", "classe": ["equity"]}, p)
    append_record({"facteur": "momentum", "classe": ["crypto"]}, p)
    append_record({"facteur": "value", "classe": ["equity"]}, p)
    assert trial_count(p) == 3
    assert trial_count(p, facteur="momentum") == 2
    assert trial_count(p, classe="crypto") == 1


def test_best_by_dsr_sorted(tmp_path):
    p = tmp_path / "h.jsonl"
    for f, d in (("a", 0.1), ("b", 0.9), ("c", 0.5)):
        append_record({"facteur": f, "dsr": d}, p)
    top = best_by_dsr(p, top=2)
    assert [r["facteur"] for r in top] == ["b", "c"]


def test_summary(tmp_path):
    p = tmp_path / "h.jsonl"
    append_record({"facteur": "a", "dsr": 0.01}, p)
    append_record({"facteur": "b", "dsr": 0.7}, p)
    s = summary(p)
    assert s["n_trials"] == 2 and s["n_robust"] == 1 and s["best_dsr"] == 0.7
