"""
Unit tests for DOM heuristic rules and contrast calculations.
"""

from backend.dom.rules import (
    calculate_contrast_ratio,
    parse_rgb,
    SENSITIVE_OPT_IN_KEYWORDS,
    FEE_DISCLAIMER_KEYWORDS,
)


def test_contrast_ratio_calculation():
    # Pure black on pure white -> 21:1
    ratio_max = calculate_contrast_ratio("rgb(0, 0, 0)", "rgb(255, 255, 255)")
    assert ratio_max >= 20.0

    # Low contrast gray on white (e.g. #cbd5e1 or rgb(203, 213, 225))
    ratio_low = calculate_contrast_ratio("rgb(203, 213, 225)", "rgb(255, 255, 255)")
    assert ratio_low < 3.0

    # Same color -> 1:1
    ratio_identical = calculate_contrast_ratio("#ffffff", "#ffffff")
    assert ratio_identical == 1.0


def test_parse_rgb_formats():
    assert parse_rgb("#000000") == (0.0, 0.0, 0.0, 1.0)
    assert parse_rgb("#ffffff") == (1.0, 1.0, 1.0, 1.0)
    assert parse_rgb("rgb(255, 0, 0)") == (1.0, 0.0, 0.0, 1.0)
    assert parse_rgb("rgba(0, 128, 0, 0.5)") == (0.0, 128 / 255.0, 0.0, 0.5)


def test_sensitive_opt_in_keywords():
    label = "Add 2-year damage protection insurance to cart"
    assert any(kw in label.lower() for kw in SENSITIVE_OPT_IN_KEYWORDS)

    clean_label = "I am over 18 years old"
    assert not any(kw in clean_label.lower() for kw in SENSITIVE_OPT_IN_KEYWORDS)


def test_fee_disclaimer_keywords():
    disclaimer = "A mandatory destination processing fee of $15 is charged upon arrival"
    assert any(kw in disclaimer.lower() for kw in FEE_DISCLAIMER_KEYWORDS)
