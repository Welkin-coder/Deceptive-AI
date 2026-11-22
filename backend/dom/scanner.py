"""
Async and Static DOM Scanner using BeautifulSoup4 and Playwright.
Extracts page structures and audits UI traps across four core categories:
1. False Urgency: Countdowns and artificial stock limits.
2. Confirm-Shaming: Emotionally manipulative decline buttons.
3. Hidden Costs: Pre-checked add-on boxes and mismatched price totals/drip fees.
4. Visual Disguise: Low-contrast or hidden opt-out options.

Returns a strict JSON schema containing a list of detected items, including
their type, severity, matched_text, and a CSS selector to locate them in the DOM.
"""

from __future__ import annotations
import asyncio
import time
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup, Tag
from playwright.async_api import async_playwright, Browser, Page

from backend.config import settings
from backend.schemas.models import (
    DarkPatternCategory,
    SeverityLevel,
    RemediationActionType,
    RemediationDirective,
    BoundingBox,
    PatternFinding,
    ScanReport,
)
from backend.dom.rules import (
    match_false_urgency,
    match_confirm_shaming,
    calculate_contrast_ratio,
    parse_inline_style,
    extract_monetary_values,
    RE_FEE_DISCLAIMER,
    SENSITIVE_OPT_IN_KEYWORDS,
    OPTOUT_KEYWORDS,
)
from backend.nlp.auditor import NLPAuditor


class DOMScanner:
    """
    Parses HTML strings and live web pages with BeautifulSoup and Playwright,
    extracting text nodes and executing rules.py NLP detection logic.
    """

    def __init__(self, nlp_auditor: Optional[NLPAuditor] = None):
        self.nlp_auditor = nlp_auditor or NLPAuditor(settings.SPACY_MODEL)

    def scan_html(self, html_content: str, target: str = "html_string") -> ScanReport:
        """
        Accepts raw HTML strings, parses with BeautifulSoup, extracts pre-checked
        boxes and text nodes, passes through rules.py NLP logic, and returns a
        strict ScanReport containing detected items.
        """
        start_time = time.perf_counter()
        findings = self.scan_html_content(html_content)
        unique_findings = self._deduplicate_findings(findings)

        risk_score = self._calculate_risk_score(unique_findings)
        risk_level = self._determine_risk_level(risk_score)

        by_category: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}
        directives: List[RemediationDirective] = []

        for f in unique_findings:
            cat = f.type
            sev = f.severity.value
            by_category[cat] = by_category.get(cat, 0) + 1
            by_severity[sev] = by_severity.get(sev, 0) + 1
            directives.append(f.remediation)

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return ScanReport(
            target=target,
            scan_type="mock_html" if "snippet" in target or "test" in target else "html_string",
            page_title="DOM HTML Audit",
            risk_score=risk_score,
            risk_level=risk_level,
            total_findings=len(unique_findings),
            findings_by_category=by_category,
            findings_by_severity=by_severity,
            findings=unique_findings,
            remediation_directives=directives,
            execution_time_ms=elapsed_ms,
        )

    async def scan_url(
        self,
        url: str,
        timeout_ms: int = 30000,
        wait_for_network_idle: bool = False,
        html: Optional[str] = None,
    ) -> ScanReport:
        """
        Audits a web page. If client-side raw HTML is provided (from content_script.js),
        directly parses it using BeautifulSoup. Otherwise, executes Playwright browser navigation.
        """
        # Fast-path: client extension sent the live extracted DOM HTML
        if html:
            return self.scan_html(html, target=url)

        start_time = time.perf_counter()
        findings: List[PatternFinding] = []
        page_title: Optional[str] = None

        async with async_playwright() as p:
            browser: Browser = await p.chromium.launch(
                headless=settings.PLAYWRIGHT_HEADLESS,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
            )
            try:
                page: Page = await browser.new_page(
                    viewport={"width": settings.VIEWPORT_WIDTH, "height": settings.VIEWPORT_HEIGHT},
                    user_agent=settings.USER_AGENT,
                )

                wait_until = "networkidle" if wait_for_network_idle else "domcontentloaded"
                await page.goto(url, wait_until=wait_until, timeout=timeout_ms)
                await page.wait_for_timeout(1000)

                page_title = await page.title()
                html_content = await page.content()

                # 1. Structural DOM heuristic scan using Playwright live evaluation
                dom_findings = await self._scan_dom_traps_playwright(page)
                findings.extend(dom_findings)

                # 2. BeautifulSoup4 structural validation & text extraction
                bs4_findings = self.scan_html_content(html_content)
                findings.extend(bs4_findings)

            finally:
                await browser.close()

        unique_findings = self._deduplicate_findings(findings)
        risk_score = self._calculate_risk_score(unique_findings)
        risk_level = self._determine_risk_level(risk_score)

        by_category: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}
        remediation_directives: List[RemediationDirective] = []

        for f in unique_findings:
            cat = f.type
            sev = f.severity.value
            by_category[cat] = by_category.get(cat, 0) + 1
            by_severity[sev] = by_severity.get(sev, 0) + 1
            remediation_directives.append(f.remediation)

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return ScanReport(
            target=url,
            scan_type="url",
            page_title=page_title,
            risk_score=risk_score,
            risk_level=risk_level,
            total_findings=len(unique_findings),
            findings_by_category=by_category,
            findings_by_severity=by_severity,
            findings=unique_findings,
            remediation_directives=remediation_directives,
            execution_time_ms=elapsed_ms,
        )

    def scan_html_content(self, html_content: str) -> List[PatternFinding]:
        """
        Core DOM evaluation engine executing the 4 category detectors on a parsed BeautifulSoup tree.
        """
        soup = BeautifulSoup(html_content, "html.parser")
        findings: List[PatternFinding] = []

        # 1. ⏳ False Urgency (Countdowns and artificial stock limits)
        findings.extend(self.detect_false_urgency(soup))

        # 2. 🙈 Confirm-Shaming (Emotionally manipulative decline copy)
        findings.extend(self.detect_confirm_shaming(soup))

        # 3. 📦 Hidden Costs (Pre-checked add-on boxes + mismatched price totals/drip fees)
        findings.extend(self.detect_hidden_costs(soup))

        # 4. 👁️ Visual Disguise (Low-contrast or hidden opt-out options)
        findings.extend(self.detect_visual_disguise(soup))

        return findings

    # =========================================================================
    # 1. ⏳ FALSE URGENCY DETECTOR
    # =========================================================================
    def detect_false_urgency(self, soup: BeautifulSoup) -> List[PatternFinding]:
        """
        Extracts countdown timer containers and text nodes, matching them
        against rules.py NLP false urgency rules.
        """
        findings: List[PatternFinding] = []
        idx = 0

        # A. Timer containers
        timer_selectors = [
            ".timer", ".countdown", "#timer", "#countdown",
            "[data-timer]", "[data-countdown]", ".urgency-badge", ".scarcity-badge",
            ".flash-sale", ".deal-timer"
        ]
        timer_elements = soup.select(", ".join(timer_selectors))

        for el in timer_elements:
            if self._is_shield_widget(el):
                continue
            text = el.get_text(strip=True)
            sel = self._generate_selector(el)
            idx += 1
            findings.append(
                PatternFinding(
                    id=f"urgency-timer-{idx}",
                    type="false_urgency",
                    category=DarkPatternCategory.FALSE_URGENCY,
                    pattern_name="High-Pressure Countdown Mechanism",
                    severity=SeverityLevel.HIGH,
                    confidence=0.92,
                    selector=sel,
                    tag_name=el.name,
                    matched_text=text or "Dynamic Countdown Timer",
                    deceptive_text=text or "Dynamic Countdown Timer",
                    explanation=f"Detected timer container '{sel}' displaying countdown to accelerate user conversion.",
                    remediation=RemediationDirective(
                        action=RemediationActionType.FREEZE_COUNTDOWN,
                        target_selector=sel,
                        css_overrides={"filter": "grayscale(100%)", "opacity": "0.7"},
                        explanation="Freeze countdown mechanism to neutralize artificial time pressure.",
                    ),
                )
            )

        # B. Extract text nodes and evaluate against rules.py NLP matching
        all_text_elements = soup.find_all(["p", "div", "span", "h1", "h2", "h3", "h4", "small", "b", "strong"])
        for node in all_text_elements:
            if self._is_shield_widget(node) or len(node.find_all(True)) > 2:
                continue
            text = node.get_text(strip=True)
            if not text or len(text) < 4:
                continue

            match_res = match_false_urgency(text)
            if match_res and not any(f.selector == self._generate_selector(node) for f in findings):
                idx += 1
                sel = self._generate_selector(node)
                is_clock = match_res.get("subtype") == "countdown" or any(c in match_res["matched_text"] for c in [":", "expires", "ends"])
                findings.append(
                    PatternFinding(
                        id=f"urgency-text-{idx}",
                        type="false_urgency",
                        category=DarkPatternCategory.FALSE_URGENCY,
                        pattern_name="Manufactured Scarcity / Artificial Stock Limit" if not is_clock else "Countdown Pressure Indicator",
                        severity=SeverityLevel.HIGH,
                        confidence=match_res.get("confidence", 0.92),
                        selector=sel,
                        tag_name=node.name,
                        matched_text=text,
                        deceptive_text=text,
                        explanation=f"Text '{text}' applies artificial psychological pressure or scarcity cues.",
                        remediation=RemediationDirective(
                            action=RemediationActionType.FREEZE_COUNTDOWN if is_clock else RemediationActionType.ALERT_BOX,
                            target_selector=sel,
                            css_overrides={"border": "2px dashed #f59e0b", "background-color": "rgba(245, 158, 11, 0.08)"},
                            explanation="Overlay informational badge warning user of artificial urgency claim.",
                        ),
                    )
                )

        return findings

    # =========================================================================
    # 2. 🙈 CONFIRM-SHAMING DETECTOR
    # =========================================================================
    def detect_confirm_shaming(self, soup: BeautifulSoup) -> List[PatternFinding]:
        """
        Extracts interactive decline elements and passes them through rules.py
        confirm-shaming matching logic.
        """
        findings: List[PatternFinding] = []
        interactive_nodes = []
        for tag in soup.find_all(["button", "a", "input", "div", "span"]):
            if tag.name in ["button", "a", "input"]:
                interactive_nodes.append(tag)
            elif tag.get("role") == "button" or any("btn" in c or "button" in c or "decline" in c for c in tag.get("class", [])):
                if not tag.find(["button", "a", "input"]):
                    interactive_nodes.append(tag)
            elif not tag.find(["button", "a", "input"]):
                interactive_nodes.append(tag)

        idx = 0
        for node in interactive_nodes:
            if self._is_shield_widget(node):
                continue
            text = (node.get_text(strip=True) if node.name != "input" else node.get("value", "")).strip()
            if not text or len(text) < 4 or len(text) > 300:
                continue

            match_res = match_confirm_shaming(text)
            if match_res:
                idx += 1
                sel = self._generate_selector(node)
                findings.append(
                    PatternFinding(
                        id=f"confirm-shame-{idx}",
                        type="confirm_shaming",
                        category=DarkPatternCategory.CONFIRM_SHAMING,
                        pattern_name="Confirm-Shaming (Manipulink)",
                        severity=SeverityLevel.HIGH,
                        confidence=match_res.get("confidence", 0.96),
                        selector=sel,
                        tag_name=node.name,
                        matched_text=text,
                        deceptive_text=text,
                        explanation=f"The decline option '{text}' emotionally manipulates the user with guilt or shame.",
                        remediation=RemediationDirective(
                            action=RemediationActionType.NEUTRALIZE_TEXT,
                            target_selector=sel,
                            replacement_text=match_res.get("replacement_text", "No, thanks"),
                            css_overrides={"font-weight": "normal", "text-decoration": "none"},
                            explanation="Rewrite emotionally manipulative copy to objective label 'No, thanks'.",
                        ),
                    )
                )

        return findings

    # =========================================================================
    # 3. 📦 HIDDEN COSTS DETECTOR
    # =========================================================================
    def detect_hidden_costs(self, soup: BeautifulSoup) -> List[PatternFinding]:
        """
        Uses BeautifulSoup to:
        A. Find all <input type="checkbox" checked> that might be hidden add-ons.
        B. Detect fine-print drip fees and mismatched price totals.
        """
        findings: List[PatternFinding] = []
        idx = 0

        # A. Find all <input type="checkbox" checked> that might be hidden add-ons
        checkboxes = soup.find_all("input", attrs={"type": lambda t: t in ["checkbox", "radio"]})
        for cb in checkboxes:
            if self._is_shield_widget(cb):
                continue
            is_checked = cb.has_attr("checked") or cb.get("checked") == "checked"
            if not is_checked:
                continue

            label_text = ""
            cb_id = cb.get("id")
            if cb_id:
                lbl = soup.find("label", attrs={"for": cb_id})
                if lbl:
                    label_text = lbl.get_text(strip=True)
            if not label_text and cb.parent:
                label_text = cb.parent.get_text(strip=True)

            label_lower = label_text.lower()
            is_sensitive_optin = any(kw in label_lower for kw in SENSITIVE_OPT_IN_KEYWORDS) or len(label_text) > 4

            if is_sensitive_optin:
                idx += 1
                sel = self._generate_selector(cb)
                findings.append(
                    PatternFinding(
                        id=f"hidden-cost-precheck-{idx}",
                        type="hidden_costs",
                        category=DarkPatternCategory.HIDDEN_COSTS,
                        pattern_name="Pre-Checked Add-On / Sneak Into Basket",
                        severity=SeverityLevel.HIGH,
                        confidence=0.95,
                        selector=sel,
                        tag_name="input",
                        attributes={"id": cb_id or "", "name": cb.get("name", ""), "type": cb.get("type", "checkbox")},
                        matched_text=label_text or "Pre-checked opt-in input",
                        deceptive_text=label_text or "Pre-checked opt-in input",
                        explanation=f"Checkbox '{label_text}' is checked by default without affirmative consent.",
                        remediation=RemediationDirective(
                            action=RemediationActionType.UNCHECK,
                            target_selector=sel,
                            explanation="Automatically uncheck pre-selected option to require active consent.",
                        ),
                    )
                )

        # B. Drip Pricing Disclaimers (word boundary matching via RE_FEE_DISCLAIMER)
        fee_nodes = soup.find_all(["p", "span", "small", "div", "em", "b", "strong"])
        for node in fee_nodes:
            if self._is_shield_widget(node) or len(node.find_all(True)) > 2:
                continue
            text = node.get_text(strip=True)
            if not text or len(text) < 6:
                continue

            has_fee_word = bool(RE_FEE_DISCLAIMER.search(text))
            has_currency = any(curr in text for curr in ["$", "€", "£", "usd", "eur"])
            has_small_style = False

            style_map = parse_inline_style(node.get("style"))
            if "font-size" in style_map:
                try:
                    import re
                    fs = float(re.sub(r"[^\d.]", "", style_map["font-size"]))
                    if fs <= 12:
                        has_small_style = True
                except ValueError:
                    pass

            if has_fee_word and (has_currency or has_small_style or node.name in ["small", "em"]):
                idx += 1
                sel = self._generate_selector(node)
                findings.append(
                    PatternFinding(
                        id=f"hidden-cost-fee-{idx}",
                        type="hidden_costs",
                        category=DarkPatternCategory.HIDDEN_COSTS,
                        pattern_name="Concealed Surcharge / Drip Pricing",
                        severity=SeverityLevel.CRITICAL,
                        confidence=0.91,
                        selector=sel,
                        tag_name=node.name,
                        matched_text=text,
                        deceptive_text=text,
                        explanation=f"Fine-print disclaimer '{text}' reveals ancillary mandatory fees.",
                        remediation=RemediationDirective(
                            action=RemediationActionType.EXPOSE_HIDDEN_FEE,
                            target_selector=sel,
                            css_overrides={
                                "display": "block",
                                "font-size": "15px",
                                "font-weight": "bold",
                                "color": "#dc2626",
                                "background-color": "#fef2f2",
                                "border": "2px solid #ef4444",
                                "padding": "8px",
                                "margin": "8px 0",
                                "border-radius": "6px",
                            },
                            explanation="Elevate hidden fee disclosure into primary purchase calculation block.",
                        ),
                    )
                )

        # C. Price Mismatch Traversal
        findings.extend(self._check_price_mismatch(soup))
        return findings

    def _check_price_mismatch(self, soup: BeautifulSoup) -> List[PatternFinding]:
        findings: List[PatternFinding] = []
        subtotal_node = soup.find(lambda el: el.name in ["div", "span", "p"] and "subtotal" in el.get_text(strip=True).lower())
        total_node = soup.find(lambda el: el.name in ["div", "span", "p"] and ("grand total" in el.get_text(strip=True).lower() or "total:" in el.get_text(strip=True).lower()))

        if subtotal_node and total_node and subtotal_node != total_node:
            sub_vals = extract_monetary_values(subtotal_node.get_text())
            tot_vals = extract_monetary_values(total_node.get_text())
            if sub_vals and tot_vals:
                subtotal = sub_vals[0]
                total = tot_vals[0]
                if total > subtotal:
                    diff = round(total - subtotal, 2)
                    sel = self._generate_selector(total_node)
                    diff_text = f"Subtotal: ${subtotal} vs Grand Total: ${total} (+${diff})"
                    findings.append(
                        PatternFinding(
                            id="hidden-cost-mismatch-1",
                            type="hidden_costs",
                            category=DarkPatternCategory.HIDDEN_COSTS,
                            pattern_name="Mismatched Price Total / Unexplained Surcharge",
                            severity=SeverityLevel.HIGH,
                            confidence=0.88,
                            selector=sel,
                            tag_name=total_node.name,
                            matched_text=diff_text,
                            deceptive_text=diff_text,
                            explanation=f"Displayed total (${total}) exceeds initial subtotal (${subtotal}) by ${diff} without itemization.",
                            remediation=RemediationDirective(
                                action=RemediationActionType.EXPOSE_HIDDEN_FEE,
                                target_selector=sel,
                                explanation="Display transparent itemized breakdown explaining total price discrepancy.",
                            ),
                        )
                    )
        return findings

    # =========================================================================
    # 4. 👁️ VISUAL DISGUISE DETECTOR
    # =========================================================================
    def detect_visual_disguise(self, soup: BeautifulSoup) -> List[PatternFinding]:
        findings: List[PatternFinding] = []
        action_elements = soup.find_all(["a", "button", "span", "div", "p"])
        idx = 0

        for el in action_elements:
            if self._is_shield_widget(el):
                continue
            text = el.get_text(strip=True)
            if not text or len(text) < 2 or len(text) > 200:
                continue

            text_lower = text.lower()
            if not any(kw in text_lower for kw in OPTOUT_KEYWORDS):
                continue

            style_attr = el.get("style", "")
            styles = parse_inline_style(style_attr)
            classes = el.get("class", [])
            class_str = " ".join(classes).lower() if isinstance(classes, list) else str(classes).lower()

            is_hidden = styles.get("display") == "none" or styles.get("visibility") == "hidden" or "hidden" in class_str
            is_low_opacity = False
            if "opacity" in styles:
                try:
                    if float(styles["opacity"]) < 0.65:
                        is_low_opacity = True
                except ValueError:
                    pass

            is_tiny = False
            if "font-size" in styles:
                try:
                    import re
                    if float(re.sub(r"[^\d.]", "", styles["font-size"])) <= 11:
                        is_tiny = True
                except ValueError:
                    pass

            is_low_contrast = False
            contrast_val = None
            if "color" in styles:
                bg = styles.get("background-color", styles.get("background", "rgb(255, 255, 255)"))
                contrast_val = calculate_contrast_ratio(styles["color"], bg)
                if contrast_val < settings.LOW_CONTRAST_THRESHOLD:
                    is_low_contrast = True

            if is_hidden or is_low_contrast or is_low_opacity or is_tiny or "muted" in class_str:
                idx += 1
                sel = self._generate_selector(el)
                findings.append(
                    PatternFinding(
                        id=f"visual-disguise-{idx}",
                        type="visual_disguise",
                        category=DarkPatternCategory.VISUAL_DISGUISE,
                        pattern_name="Visual Disguise & Obscured Opt-Out",
                        severity=SeverityLevel.HIGH,
                        confidence=0.93,
                        selector=sel,
                        tag_name=el.name,
                        matched_text=text,
                        deceptive_text=text,
                        explanation=f"The opt-out choice '{text}' is visually disguised or suppressed.",
                        remediation=RemediationDirective(
                            action=RemediationActionType.RESTORE_CONTRAST,
                            target_selector=sel,
                            css_overrides={
                                "display": "inline-block !important",
                                "visibility": "visible !important",
                                "opacity": "1.0 !important",
                                "color": "#111827",
                                "background-color": "#e5e7eb",
                                "font-size": "14px",
                                "font-weight": "600",
                                "border": "1px solid #9ca3af",
                                "padding": "8px 16px",
                                "border-radius": "6px",
                            },
                            explanation="Restore visibility and accessible contrast to disguised opt-out option.",
                        ),
                    )
                )

        return findings

    # =========================================================================
    # Playwright Live DOM Evaluation
    # =========================================================================
    async def _scan_dom_traps_playwright(self, page: Page) -> List[PatternFinding]:
        findings: List[PatternFinding] = []
        prechecked = await page.evaluate(
            """() => {
            const results = [];
            const inputs = Array.from(document.querySelectorAll('input[type="checkbox"], input[type="radio"]'));
            for (const input of inputs) {
                if (input.closest('#deceptive-shield-hud') || input.closest('.deceptive-uncheck-badge')) continue;
                if (input.checked) {
                    let labelText = '';
                    if (input.id) {
                        const lbl = document.querySelector(`label[for="${input.id}"]`);
                        if (lbl) labelText = lbl.innerText;
                    }
                    if (!labelText && input.parentElement) labelText = input.parentElement.innerText;

                    let sel = input.id ? `#${input.id}` : (input.name ? `input[name="${input.name}"]` : 'input[type="checkbox"]');
                    const rect = input.getBoundingClientRect();
                    results.push({ selector: sel, tag: input.tagName.toLowerCase(), labelText: labelText.trim(), rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height } });
                }
            }
            return results;
        }"""
        )

        for idx, item in enumerate(prechecked):
            text_lower = (item["labelText"] or "").lower()
            if any(kw in text_lower for kw in SENSITIVE_OPT_IN_KEYWORDS) or len(text_lower) > 4:
                findings.append(
                    PatternFinding(
                        id=f"dom-precheck-{idx+1}",
                        type="hidden_costs",
                        category=DarkPatternCategory.HIDDEN_COSTS,
                        pattern_name="Pre-Checked Default Opt-In",
                        severity=SeverityLevel.HIGH,
                        confidence=0.94,
                        selector=item["selector"],
                        tag_name=item["tag"],
                        attributes={"id": "", "name": "", "type": "checkbox"},
                        bounding_box=BoundingBox(**item["rect"]),
                        matched_text=item["labelText"] or "Pre-checked input",
                        deceptive_text=item["labelText"] or "Pre-checked input",
                        explanation=f"Option '{item['labelText']}' is checked by default without affirmative consent.",
                        remediation=RemediationDirective(
                            action=RemediationActionType.UNCHECK,
                            target_selector=item["selector"],
                            explanation="Automatically uncheck default opt-in box.",
                        ),
                    )
                )

        return findings

    def _is_shield_widget(self, el: Tag) -> bool:
        if not el or not hasattr(el, "get"):
            return False
        el_id = el.get("id", "")
        if el_id and ("deceptive" in el_id or "dark-pattern" in el_id):
            return True
        classes = el.get("class", [])
        class_str = " ".join(classes) if isinstance(classes, list) else str(classes)
        return "deceptive" in class_str or "dark-pattern" in class_str

    def _generate_selector(self, el: Tag) -> str:
        if not el or not hasattr(el, "name"):
            return "body"
        el_id = el.get("id")
        if el_id:
            return f"#{el_id}"
        classes = el.get("class", [])
        if isinstance(classes, list) and classes:
            clean_classes = [c for c in classes if not c.startswith("deceptive") and not c.startswith("dark-pattern")][:2]
            if clean_classes:
                return f"{el.name}.{'.'.join(clean_classes)}"
        name_attr = el.get("name")
        if name_attr:
            return f"{el.name}[name=\"{name_attr}\"]"
        return el.name

    def _deduplicate_findings(self, findings: List[PatternFinding]) -> List[PatternFinding]:
        deduped: List[PatternFinding] = []
        seen = set()
        for f in findings:
            key = (f.type, f.selector, f.matched_text.strip().lower()[:50])
            if key not in seen:
                seen.add(key)
                deduped.append(f)
        return deduped

    def _calculate_risk_score(self, findings: List[PatternFinding]) -> float:
        if not findings:
            return 0.0
        raw_score = sum(settings.SEVERITY_WEIGHTS.get(f.severity.value, 5.0) for f in findings)
        return round(min(100.0, raw_score * 1.5), 1)

    def _determine_risk_level(self, risk_score: float) -> str:
        if risk_score >= 60.0:
            return "SEVERE"
        elif risk_score >= 35.0:
            return "HIGH"
        elif risk_score >= 15.0:
            return "MODERATE"
        return "SAFE"
