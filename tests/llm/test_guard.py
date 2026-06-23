"""Tests du garde anti-hallucination chiffrée (LLM)."""

from packages.llm.guard import allowed_values, guard_numbers


def test_allowed_values_extracts_numbers():
    vals = allowed_values("ROCE 18.5% vs WACC 8%, score 72/100")
    assert 18.5 in vals and 8.0 in vals and 72.0 in vals


def test_redacts_fabricated_percentage():
    ctx = "ROCE 18.5% vs WACC 8%."
    txt = "Le ROCE de 18.5% dépasse le WACC ; objectif de cours +42.0%."
    clean, viol = guard_numbers(txt, ctx)
    assert "42.0%" not in clean and "[n.d.]" in clean
    assert "42.0%" in viol
    assert "18.5%" in clean                     # chiffre légitime conservé


def test_keeps_reformatted_number_within_tolerance():
    ctx = "marge de sécurité 0.23."
    txt = "La marge de sécurité ressort à 0.23 environ."
    clean, viol = guard_numbers(txt, ctx)
    assert not viol and "[n.d.]" not in clean


def test_ignores_small_enumeration_integers():
    ctx = "score 72/100."
    txt = "En 3 phrases : le score de 72 est solide."
    clean, viol = guard_numbers(txt, ctx)
    assert not viol                       # le « 3 » d'énumération n'est pas contrôlé


def test_flags_large_fabricated_value():
    ctx = "score 72/100."
    txt = "Capitalisation estimée à 1500 milliards."
    clean, viol = guard_numbers(txt, ctx)
    assert "1500" in viol and "[n.d.]" in clean


def test_reject_policy_blanks_on_violation():
    ctx = "ROCE 18.5%."
    txt = "Objectif +99.9%."
    clean, viol = guard_numbers(txt, ctx, policy="reject")
    assert clean == "" and viol
