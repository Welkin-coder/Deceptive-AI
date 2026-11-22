"""
Unit and integration tests for DOMScanner validating detection accuracy
against mock HTML snippets across the four core deceptive pattern categories:
1. ⏳ False Urgency
2. 🙈 Confirm-Shaming
3. 📦 Hidden Costs
4. 👁️ Visual Disguise
"""

import pytest
from backend.dom.scanner import DOMScanner
from backend.schemas.models import (
    DarkPatternCategory,
    SeverityLevel,
    RemediationActionType,
)


@pytest.fixture(scope="module")
def scanner():
    return DOMScanner()


# =============================================================================
# 1. ⏳ False Urgency Tests
# =============================================================================
def test_false_urgency_countdown_and_stock_limits(scanner):
    mock_html = """
    <div class="product-page">
        <h1>Wireless Earbuds</h1>
        <!-- 1. Countdown timer -->
        <div class="countdown" id="timer-box" data-timer="300">
            Offer expires in: <span id="timer">04:59</span>
        </div>
        <!-- 2. Artificial stock limit / social scarcity -->
        <p class="scarcity-warning" id="stock-notice">
            HURRY! Only 1 item left in stock - 24 people have this in their cart right now!
        </p>
        <button id="buy-btn">Buy Now</button>
    </div>
    """
    report = scanner.scan_html(mock_html, target="test_urgency_snippet")

    assert report.total_findings >= 2
    assert DarkPatternCategory.FALSE_URGENCY.value in report.findings_by_category

    # Verify countdown clock was caught and assigned FREEZE_COUNTDOWN
    timer_findings = [f for f in report.findings if f.category == DarkPatternCategory.FALSE_URGENCY and f.remediation.action == RemediationActionType.FREEZE_COUNTDOWN]
    assert len(timer_findings) >= 1

    # Verify stock limit was caught
    stock_findings = [f for f in report.findings if f.category == DarkPatternCategory.FALSE_URGENCY and "Only 1 item left" in f.deceptive_text]
    assert len(stock_findings) >= 1
    assert stock_findings[0].remediation.action == RemediationActionType.ALERT_BOX


# =============================================================================
# 2. 🙈 Confirm-Shaming Tests
# =============================================================================
def test_confirm_shaming_classification(scanner):
    mock_html = """
    <div class="modal-dialogue">
        <h2>Special 50% Discount Just For You!</h2>
        <button class="btn-primary" id="claim-btn">Claim My 50% Savings</button>
        <!-- Emotionally manipulative decline link -->
        <a href="#" id="shame-decline" class="decline-link">
            No thanks, I hate saving money and I prefer paying full price
        </a>
    </div>
    """
    report = scanner.scan_html(mock_html, target="test_confirm_shaming_snippet")

    assert report.total_findings >= 1
    shame_finding = next((f for f in report.findings if f.category == DarkPatternCategory.CONFIRM_SHAMING), None)
    assert shame_finding is not None
    assert shame_finding.selector == "#shame-decline"
    assert shame_finding.remediation.action == RemediationActionType.NEUTRALIZE_TEXT
    assert "No, thanks" in shame_finding.remediation.replacement_text


# =============================================================================
# 3. 📦 Hidden Costs Tests
# =============================================================================
def test_hidden_costs_prechecked_addon_boxes(scanner):
    mock_html = """
    <form id="checkout-form">
        <h3>Order Add-ons</h3>
        <!-- Pre-checked commercial add-on -->
        <div class="addon-item">
            <input type="checkbox" id="warranty-checkbox" checked="checked" />
            <label for="warranty-checkbox">Add 2-Year Damage Protection Warranty & Insurance (+$9.99)</label>
        </div>
        <!-- Pre-checked marketing opt-in -->
        <div class="addon-item">
            <input type="checkbox" id="partner-marketing" checked />
            <label for="partner-marketing">Agree to receive promotional partner newsletters</label>
        </div>
        <!-- Ethical non-prechecked box -->
        <div class="addon-item">
            <input type="checkbox" id="terms-agree" />
            <label for="terms-agree">I agree to the standard Terms of Service</label>
        </div>
    </form>
    """
    report = scanner.scan_html(mock_html, target="test_hidden_costs_precheck")

    assert report.total_findings >= 2
    assert DarkPatternCategory.HIDDEN_COSTS.value in report.findings_by_category

    # Verify pre-checked boxes are flagged with UNCHECK remediation
    precheck_findings = [f for f in report.findings if f.category == DarkPatternCategory.HIDDEN_COSTS and f.remediation.action == RemediationActionType.UNCHECK]
    selectors = [f.selector for f in precheck_findings]
    assert "#warranty-checkbox" in selectors
    assert "#partner-marketing" in selectors
    # Ensure ethical unchecked terms box was NOT flagged
    assert "#terms-agree" not in selectors


def test_hidden_costs_price_mismatch_and_drip_fees(scanner):
    mock_html = """
    <div class="cart-summary">
        <span class="subtotal">Subtotal: $50.00</span>
        <span class="grand-total" id="final-total">Grand Total: $65.00</span>
        <!-- Concealed surcharge fine print -->
        <small class="fee-fineprint" id="processing-fee">
            * A mandatory non-refundable processing fee of $15.00 applies at checkout.
        </small>
    </div>
    """
    report = scanner.scan_html(mock_html, target="test_hidden_costs_mismatch")

    assert report.total_findings >= 1
    hidden_fee_findings = [f for f in report.findings if f.category == DarkPatternCategory.HIDDEN_COSTS]
    assert len(hidden_fee_findings) >= 1
    assert any(f.remediation.action == RemediationActionType.EXPOSE_HIDDEN_FEE for f in hidden_fee_findings)


# =============================================================================
# 4. 👁️ Visual Disguise Tests
# =============================================================================
def test_visual_disguise_low_contrast_and_hidden_optout(scanner):
    mock_html = """
    <div class="cookie-banner">
        <h2>We Value Your Privacy</h2>
        <button class="accept-btn" style="background-color: #16a34a; color: #ffffff; font-size: 16px;">
            Accept All Cookies
        </button>
        <!-- 1. Low contrast & tiny opt-out -->
        <a href="#" id="low-contrast-reject" style="color: #cbd5e1; background-color: #ffffff; font-size: 9px; opacity: 0.4;">
            Reject non-essential tracking cookies
        </a>
        <!-- 2. Completely hidden opt-out -->
        <div id="hidden-cancel" style="display: none;">
            Cancel and opt-out of data sharing
        </div>
    </div>
    """
    report = scanner.scan_html(mock_html, target="test_visual_disguise")

    assert report.total_findings >= 2
    assert DarkPatternCategory.VISUAL_DISGUISE.value in report.findings_by_category

    disguise_findings = [f for f in report.findings if f.category == DarkPatternCategory.VISUAL_DISGUISE]
    selectors = [f.selector for f in disguise_findings]
    assert "#low-contrast-reject" in selectors
    assert "#hidden-cancel" in selectors

    # Remediation should be RESTORE_CONTRAST with accessible style overrides
    for f in disguise_findings:
        assert f.remediation.action == RemediationActionType.RESTORE_CONTRAST
        assert "display" in f.remediation.css_overrides or "opacity" in f.remediation.css_overrides


# =============================================================================
# 5. Benign HTML (Zero False Positives)
# =============================================================================
def test_benign_html_clean_baseline(scanner):
    mock_html = """
    <div class="store-page">
        <h1>Clean Organic Coffee</h1>
        <p style="color: #111827; background-color: #ffffff; font-size: 16px;">
            Single-origin whole bean coffee. Free standard shipping on orders over $40.
        </p>
        <button style="background-color: #2563eb; color: #ffffff; font-size: 15px; padding: 10px 20px;">
            Add to Cart
        </button>
        <a href="/cart" style="color: #1e40af; font-size: 14px; text-decoration: underline;">
            Cancel and Return to Catalog
        </a>
        <input type="checkbox" id="clean-terms" />
        <label for="clean-terms">I agree to terms of service</label>
    </div>
    """
    report = scanner.scan_html(mock_html, target="test_benign_clean")

    assert report.total_findings == 0
    assert report.risk_score == 0.0
    assert report.risk_level == "SAFE"
