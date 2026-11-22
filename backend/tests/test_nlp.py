"""
Unit tests for the spaCy NLP Manipulative Language Auditor.
"""

import pytest
from backend.nlp.auditor import NLPAuditor
from backend.schemas.models import DarkPatternCategory, SeverityLevel


@pytest.fixture(scope="module")
def auditor():
    return NLPAuditor("en_core_web_sm")


def test_false_urgency_detection(auditor):
    text = "HURRY! Only 1 left in stock. 24 people are viewing this right now!"
    findings = auditor.analyze_text(text, element_selector="#urgency-banner")

    assert len(findings) >= 1
    categories = [f.category for f in findings]
    assert DarkPatternCategory.FALSE_URGENCY in categories
    assert any(f.severity == SeverityLevel.HIGH for f in findings)


def test_confirm_shaming_detection(auditor):
    text = "No thanks, I hate saving money and I prefer paying full price"
    findings = auditor.analyze_text(text, element_selector="#decline-link", context_hint="button")

    assert len(findings) >= 1
    shame_finding = next((f for f in findings if f.category == DarkPatternCategory.CONFIRM_SHAMING), None)
    assert shame_finding is not None
    assert shame_finding.remediation.action.value == "neutralize_text"
    assert "No, thanks" in shame_finding.remediation.replacement_text


def test_hidden_fees_language(auditor):
    text = "A non-refundable processing fee of $14.99 applies at checkout."
    findings = auditor.analyze_text(text, element_selector="#fee-note")

    assert len(findings) >= 1
    fee_finding = next((f for f in findings if f.category == DarkPatternCategory.HIDDEN_FEES), None)
    assert fee_finding is not None
    assert fee_finding.severity == SeverityLevel.CRITICAL


def test_forced_continuity_language(auditor):
    text = "Your card will be billed annually after 7-day trial period unless cancelled."
    findings = auditor.analyze_text(text, element_selector="#terms")

    assert len(findings) >= 1
    continuity_finding = next((f for f in findings if f.category == DarkPatternCategory.FORCED_CONTINUITY), None)
    assert continuity_finding is not None


def test_trick_question_double_negative(auditor):
    text = "Uncheck if you do not want to receive updates from our partners."
    findings = auditor.analyze_text(text, element_selector="#checkbox-label")

    assert len(findings) >= 1
    trick_finding = next((f for f in findings if f.category == DarkPatternCategory.TRICK_QUESTIONS), None)
    assert trick_finding is not None


def test_benign_text_produces_no_false_positives(auditor):
    benign_text = "Welcome to our store. We ship orders within 2 business days via FedEx ground."
    findings = auditor.analyze_text(benign_text, element_selector="p")
    assert len(findings) == 0
