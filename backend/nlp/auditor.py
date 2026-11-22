"""
NLP Auditing Engine using spaCy (en_core_web_sm).
Detects manipulative language, deceptive psychological cues, false urgency,
confirm-shaming, drip fee disclaimers, and trick phrasing.
"""

from __future__ import annotations
import re
import spacy
from spacy.matcher import Matcher
from typing import List, Dict, Any, Optional

from backend.schemas.models import (
    DarkPatternCategory,
    SeverityLevel,
    RemediationActionType,
    RemediationDirective,
    PatternFinding,
)


class NLPAuditor:
    """
    Analyzes web page text copy, button labels, modal dialogues,
    and fine-print disclaimers using spaCy linguistic analysis.
    """

    def __init__(self, model_name: str = "en_core_web_sm"):
        try:
            self.nlp = spacy.load(model_name)
        except Exception:
            # Fallback if pipeline packaging varies
            import en_core_web_sm
            self.nlp = en_core_web_sm.load()

        self.matcher = Matcher(self.nlp.vocab)
        self._init_matchers()

    def _init_matchers(self):
        """Register token-level and phrase-level detection patterns into spaCy Matcher."""
        
        # 1. FALSE URGENCY: Numerical scarcity (e.g., "Only 1 left!", "Just 2 items remaining")
        self.matcher.add(
            "FALSE_URGENCY_NUM_SCARCITY",
            [
                [
                    {"LOWER": {"IN": ["only", "just", "merely"]}},
                    {"LIKE_NUM": True},
                    {"LOWER": {"IN": ["left", "remaining", "available", "rooms", "items", "seats", "tickets", "copies"]}},
                ],
                [
                    {"LIKE_NUM": True},
                    {"LOWER": {"IN": ["items", "rooms", "seats", "tickets"]}},
                    {"LOWER": "left"},
                    {"LOWER": "in"},
                    {"LOWER": "stock", "OP": "?"},
                ],
            ],
        )

        # 2. FALSE URGENCY: Time-pressure triggers (e.g., "Hurry, offer expires in 5 minutes", "Act now or lose out")
        self.matcher.add(
            "FALSE_URGENCY_TIME_PRESSURE",
            [
                [
                    {"LOWER": {"IN": ["hurry", "rush", "act", "claim"]}},
                    {"LOWER": {"IN": ["now", "fast", "today", "quick"]}},
                ],
                [
                    {"LOWER": {"IN": ["limited", "last"]}},
                    {"LOWER": {"IN": ["time", "chance", "call", "opportunity", "hours"]}},
                ],
                [
                    {"LOWER": {"IN": ["offer", "deal", "discount", "sale"]}},
                    {"LOWER": {"IN": ["expires", "ends", "closing"]}},
                ],
                [
                    {"LOWER": "selling"},
                    {"LOWER": "fast"},
                ],
                [
                    {"LOWER": "almost"},
                    {"LOWER": {"IN": ["sold", "gone"]}},
                ],
            ],
        )

        # 3. FALSE URGENCY: Social proof pressure (e.g., "18 people are looking at this right now")
        self.matcher.add(
            "FALSE_URGENCY_SOCIAL_PRESSURE",
            [
                [
                    {"LIKE_NUM": True},
                    {"LOWER": {"IN": ["people", "viewers", "shoppers", "customers", "users"]}},
                    {"LOWER": {"IN": ["viewing", "watching", "looking", "have"]}},
                ],
                [
                    {"LOWER": {"IN": ["high", "heavy"]}},
                    {"LOWER": "demand"},
                ],
                [
                    {"LOWER": "in"},
                    {"LOWER": "high"},
                    {"LOWER": "demand"},
                ],
                [
                    {"LOWER": "booked"},
                    {"LIKE_NUM": True},
                    {"LOWER": "times"},
                ],
            ],
        )

        # 4. CONFIRM-SHAMING: Explicit emotional guilt / self-deprecating opt-out
        # (e.g., "No thanks, I hate saving money", "No, I prefer paying full price", "I don't care about my health")
        self.matcher.add(
            "CONFIRM_SHAMING_HATE_SAVINGS",
            [
                [
                    {"LOWER": "i"},
                    {"LOWER": {"IN": ["hate", "loathe", "dislike"]}},
                    {"LOWER": {"IN": ["saving", "savings", "discounts", "money", "deals", "gifts", "rewards"]}},
                ],
                [
                    {"LOWER": "no"},
                    {"IS_PUNCT": True, "OP": "?"},
                    {"LOWER": "thanks", "OP": "?"},
                    {"IS_PUNCT": True, "OP": "?"},
                    {"LOWER": "i"},
                    {"LOWER": {"IN": ["hate", "loathe", "prefer", "dont", "don't"]}},
                ],
                [
                    {"LOWER": {"IN": ["prefer", "rather"]}},
                    {"LOWER": {"IN": ["paying", "to", "pay"]}},
                    {"LOWER": {"IN": ["full", "more", "regular"]}},
                    {"LOWER": {"IN": ["price", "cost", "amount", "rate"]}},
                ],
                [
                    {"LOWER": "i"},
                    {"LOWER": {"IN": ["dont", "don't"]}},
                    {"LOWER": {"IN": ["care", "want", "need"]}},
                    {"LOWER": {"IN": ["about", "to", "my", "any", "free"]}},
                    {"LOWER": {"IN": ["saving", "savings", "health", "security", "money", "discounts", "rewards", "protect"]}},
                ],
                [
                    {"LOWER": "i"},
                    {"LOWER": "like"},
                    {"LOWER": "being"},
                    {"LOWER": {"IN": ["poor", "broke", "unprotected", "unhealthy"]}},
                ],
            ],
        )

        # 5. HIDDEN FEES / DRIP PRICING: fine-print fee cues
        self.matcher.add(
            "HIDDEN_FEES_LANGUAGE",
            [
                [
                    {"LOWER": {"IN": ["mandatory", "additional", "hidden", "processing", "handling", "service"]}},
                    {"LOWER": {"IN": ["fee", "fees", "surcharge", "charge", "charges"]}},
                    {"LOWER": {"IN": ["apply", "applies", "added", "required", "checkout"]}, "OP": "?"},
                ],
                [
                    {"LOWER": "non-refundable"},
                    {"LOWER": {"IN": ["fee", "charge", "deposit"]}},
                ],
            ],
        )

        # 6. FORCED CONTINUITY: recurring stealth renewal language
        self.matcher.add(
            "FORCED_CONTINUITY_LANGUAGE",
            [
                [
                    {"LOWER": {"IN": ["automatically", "auto"]}},
                    {"LOWER": {"IN": ["renews", "renew", "renewing", "recurring"]}},
                ],
                [
                    {"LOWER": {"IN": ["billed", "charged"]}},
                    {"LOWER": {"IN": ["annually", "monthly", "after"]}},
                    {"LOWER": {"IN": ["trial", "free", "period", "promo"]}, "OP": "?"},
                ],
                [
                    {"LOWER": "unless"},
                    {"LOWER": {"IN": ["cancelled", "canceled", "opt-out"]}},
                ],
            ],
        )

        # 7. TRICK QUESTIONS / DOUBLE NEGATIVES:
        # e.g., "Uncheck if you do not want", "Do not untick if you wish"
        self.matcher.add(
            "TRICK_QUESTION_DOUBLE_NEGATIVE",
            [
                [
                    {"LOWER": {"IN": ["uncheck", "untick", "deselect"]}},
                    {"LOWER": "if"},
                    {"LOWER": "you"},
                    {"LOWER": "do"},
                    {"LOWER": "not"},
                ],
                [
                    {"LOWER": "do"},
                    {"LOWER": "not"},
                    {"LOWER": {"IN": ["uncheck", "untick", "deselect"]}},
                ],
            ],
        )

    def analyze_text(
        self,
        text: str,
        element_selector: str = "body",
        context_hint: str = "generic"
    ) -> List[PatternFinding]:
        """
        Runs spaCy linguistic analysis and matcher rules on target string.
        Returns a list of structured PatternFinding objects.
        """
        clean_text = text.strip()
        if not clean_text or len(clean_text) < 3:
            return []

        doc = self.nlp(clean_text)
        matches = self.matcher(doc)
        findings: List[PatternFinding] = []
        seen_spans = set()

        for match_id, start, end in matches:
            rule_name = self.nlp.vocab.strings[match_id]
            span = doc[start:end]
            span_text = span.text

            # Avoid reporting duplicated overlapping spans
            span_key = (rule_name, start, end)
            if any(s <= start and e >= end for (r, s, e) in seen_spans if r == rule_name):
                continue
            seen_spans.add(span_key)

            finding = self._build_finding_from_rule(
                rule_name=rule_name,
                matched_span=span_text,
                full_sentence=span.sent.text.strip(),
                element_selector=element_selector,
                context_hint=context_hint,
                finding_index=len(findings) + 1,
            )
            if finding:
                findings.append(finding)

        # Additional semantic / dependency parsing heuristics for confirm-shaming
        if context_hint in ("button", "link", "modal", "generic"):
            shaming_finding = self._check_dependency_confirm_shaming(doc, clean_text, element_selector, len(findings) + 1)
            if shaming_finding and not any(f.category == DarkPatternCategory.CONFIRM_SHAMING for f in findings):
                findings.append(shaming_finding)

        # Regex heuristic check for countdown formats (e.g., "04:59", "00:15:30")
        timer_finding = self._check_countdown_timer_text(clean_text, element_selector, len(findings) + 1)
        if timer_finding and not any(f.pattern_name == "Fake Countdown Timer" for f in findings):
            findings.append(timer_finding)

        # Deduplicate findings by (category, selector, deceptive_text) to prevent clutter
        deduped: List[PatternFinding] = []
        seen_keys = set()
        for f in findings:
            key = (f.category, f.selector, f.deceptive_text.strip().lower())
            if key not in seen_keys:
                seen_keys.add(key)
                deduped.append(f)

        return deduped

    def _build_finding_from_rule(
        self,
        rule_name: str,
        matched_span: str,
        full_sentence: str,
        element_selector: str,
        context_hint: str,
        finding_index: int,
    ) -> Optional[PatternFinding]:
        """Constructs standardized PatternFinding object with actionable remediation."""

        finding_id = f"nlp-{rule_name.lower()}-{finding_index}"

        if rule_name.startswith("FALSE_URGENCY"):
            return PatternFinding(
                id=finding_id,
                category=DarkPatternCategory.FALSE_URGENCY,
                pattern_name="Manufactured Urgency & Artificial Scarcity",
                severity=SeverityLevel.HIGH,
                confidence=0.92,
                selector=element_selector,
                deceptive_text=full_sentence,
                explanation=(
                    f"The phrasing '{matched_span}' applies artificial psychological time pressure or false "
                    "scarcity heuristics to coerce hurried purchasing without rational reflection."
                ),
                remediation=RemediationDirective(
                    action=RemediationActionType.ALERT_BOX,
                    target_selector=element_selector,
                    replacement_text=None,
                    css_overrides={"border": "2px dashed #f59e0b", "background-color": "rgba(245, 158, 11, 0.08)"},
                    explanation="Mark urgency claim with disclosure badge or suppress countdown.",
                ),
            )

        elif rule_name.startswith("CONFIRM_SHAMING"):
            # Provide neutral replacement (e.g. "No thanks" or "Decline")
            neutral_text = "No, thanks"
            return PatternFinding(
                id=finding_id,
                category=DarkPatternCategory.CONFIRM_SHAMING,
                pattern_name="Confirm-Shaming (Manipulink)",
                severity=SeverityLevel.HIGH,
                confidence=0.95,
                selector=element_selector,
                deceptive_text=full_sentence,
                explanation=(
                    f"The decline option copy '{full_sentence}' emotionally manipulates the user by associating "
                    "opting out with self-deprecation, shame, or irrationality."
                ),
                remediation=RemediationDirective(
                    action=RemediationActionType.NEUTRALIZE_TEXT,
                    target_selector=element_selector,
                    replacement_text=neutral_text,
                    css_overrides={"font-weight": "normal", "text-decoration": "none"},
                    explanation=f"Rewrite emotionally manipulative copy to objective label '{neutral_text}'.",
                ),
            )

        elif rule_name.startswith("HIDDEN_FEES"):
            return PatternFinding(
                id=finding_id,
                category=DarkPatternCategory.HIDDEN_FEES,
                pattern_name="Drip Pricing / Concealed Surcharge",
                severity=SeverityLevel.CRITICAL,
                confidence=0.88,
                selector=element_selector,
                deceptive_text=full_sentence,
                explanation=(
                    f"Text contains hidden fee disclaimers ('{matched_span}') that obscure the true all-inclusive cost "
                    "until final checkout stages."
                ),
                remediation=RemediationDirective(
                    action=RemediationActionType.EXPOSE_HIDDEN_FEE,
                    target_selector=element_selector,
                    css_overrides={"display": "block", "font-size": "14px", "color": "#b91c1c", "font-weight": "bold"},
                    explanation="Elevate fee disclosure into primary price calculation block.",
                ),
            )

        elif rule_name.startswith("FORCED_CONTINUITY"):
            return PatternFinding(
                id=finding_id,
                category=DarkPatternCategory.FORCED_CONTINUITY,
                pattern_name="Forced Continuity / Silent Subscription",
                severity=SeverityLevel.CRITICAL,
                confidence=0.90,
                selector=element_selector,
                deceptive_text=full_sentence,
                explanation=(
                    f"The terms indicate automatic subscription rollover ('{matched_span}') "
                    "without requiring explicit re-confirmation."
                ),
                remediation=RemediationDirective(
                    action=RemediationActionType.ALERT_BOX,
                    target_selector=element_selector,
                    explanation="Highlight recurring billing terms prominently before payment authorization.",
                ),
            )

        elif rule_name.startswith("TRICK_QUESTION"):
            return PatternFinding(
                id=finding_id,
                category=DarkPatternCategory.TRICK_QUESTIONS,
                pattern_name="Confusing Phrasing / Double Negative",
                severity=SeverityLevel.HIGH,
                confidence=0.89,
                selector=element_selector,
                deceptive_text=full_sentence,
                explanation=(
                    f"Convoluted phrasing ('{matched_span}') causes cognitive confusion regarding whether "
                    "checking or unchecking enables or disables the option."
                ),
                remediation=RemediationDirective(
                    action=RemediationActionType.ALERT_BOX,
                    target_selector=element_selector,
                    explanation="Clarify opt-in/opt-out intention into straightforward affirmative statement.",
                ),
            )

        return None

    def _check_dependency_confirm_shaming(
        self, doc: spacy.tokens.Doc, text: str, element_selector: str, finding_index: int
    ) -> Optional[PatternFinding]:
        """
        Uses spaCy dependency parsing to catch syntax patterns like:
        [negation] + [hate/prefer/loser/waste/broke/cheap] + [benefit]
        """
        lower_text = text.lower()
        shaming_keywords = ["hate", "loathe", "prefer paying", "full price", "like being", "miss out", "pay more", "rather pay"]
        neg_words = ["no", "nah", "never", "not"]

        has_negation = any(tok.lower_ in neg_words or tok.dep_ == "neg" for tok in doc)
        has_shame_cue = any(kw in lower_text for kw in shaming_keywords)

        if has_negation and has_shame_cue:
            return PatternFinding(
                id=f"nlp-dep-confirm-shaming-{finding_index}",
                category=DarkPatternCategory.CONFIRM_SHAMING,
                pattern_name="Confirm-Shaming (Syntactic)",
                severity=SeverityLevel.HIGH,
                confidence=0.93,
                selector=element_selector,
                deceptive_text=text,
                explanation=(
                    "Semantic structure reflects confirm-shaming: users refusing an offer are forced "
                    "to click negative self-critical declarations."
                ),
                remediation=RemediationDirective(
                    action=RemediationActionType.NEUTRALIZE_TEXT,
                    target_selector=element_selector,
                    replacement_text="No, thanks",
                    explanation="Replace manipulative guilt phrasing with neutral refusal.",
                ),
            )
        return None

    def _check_countdown_timer_text(
        self, text: str, element_selector: str, finding_index: int
    ) -> Optional[PatternFinding]:
        """Detects countdown clock indicators e.g. '04:59' or 'Offer expires in: 00:10:00'."""
        timer_pattern = r"(?:expires\s+in|ends\s+in|left:?)?\s*\b(?:\d{1,2}:){1,2}\d{2}\b"
        match = re.search(timer_pattern, text, re.IGNORECASE)
        if match:
            return PatternFinding(
                id=f"nlp-timer-{finding_index}",
                category=DarkPatternCategory.FALSE_URGENCY,
                pattern_name="Fake Countdown Timer",
                severity=SeverityLevel.HIGH,
                confidence=0.90,
                selector=element_selector,
                deceptive_text=text,
                explanation="Detected ticking countdown timer creating psychological pressure to finalize transactions.",
                remediation=RemediationDirective(
                    action=RemediationActionType.FREEZE_COUNTDOWN,
                    target_selector=element_selector,
                    explanation="Freeze countdown clock and expose timer artificiality.",
                ),
            )
        return None
