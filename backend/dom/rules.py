"""
Compiled regex and spaCy matching rules for deceptive UI pattern detection.
Specialized for:
1. False Urgency (countdowns, artificial stock limits, time triggers)
2. Confirm-Shaming (emotionally manipulative decline buttons)
3. DOM heuristics (contrast math, style parsing, keyword sensitivity)
"""

from __future__ import annotations
import math
import re
from typing import Dict, Any, Optional, Tuple, List
import spacy
from spacy.matcher import Matcher

# -----------------------------------------------------------------------------
# spaCy NLP Initialization
# -----------------------------------------------------------------------------
try:
    nlp = spacy.load("en_core_web_sm")
except Exception:
    import en_core_web_sm
    nlp = en_core_web_sm.load()

matcher = Matcher(nlp.vocab)

# -----------------------------------------------------------------------------
# Compiled Regular Expressions
# -----------------------------------------------------------------------------

# 1. False Urgency & Countdown Timer Regex
RE_COUNTDOWN_TIME = re.compile(
    r"\b(?:\d{1,2}:){1,2}\d{2}\b|"
    r"\b\d+\s*(?:minutes?|hours?|seconds?|mins?|secs?)\s*(?:left|remaining)\b",
    re.IGNORECASE,
)

RE_FALSE_URGENCY_PATTERNS = re.compile(
    r"(?:"
    r"\b(?:only|just)\s+\d+\s+(?:left|remaining|items?|in\s+stock|rooms?|seats?|tickets?)\b|"
    r"\b\d+\s+(?:people|shoppers|customers|viewers|users)\s+(?:are\s+)?(?:viewing|watching|looking|have this in their cart|bought)\b|"
    r"\b(?:offer|deal|discount|sale|price)\s+(?:expires|ends)\b|"
    r"\b(?:expires\s+in|ends\s+in|sale\s+ends|deal\s+expires|hurry\b|last\s+chance|limited\s+time\s+offer|act\s+now)\b|"
    r"\b(?:almost\s+(?:sold\s+out|gone)|selling\s+fast|in\s+high\s+demand|booked\s+\d+\s+times)\b"
    r")",
    re.IGNORECASE,
)

# 2. Confirm-Shaming Manipulative Decline Regex
RE_CONFIRM_SHAMING_PATTERNS = re.compile(
    r"(?:"
    r"\b(?:hate\s+(?:saving\s+money|savings|discounts|deals|free|gifts|cashback))\b|"
    r"\b(?:prefer\s+(?:paying|to\s+pay)\s+(?:full|more|regular)\s+price)\b|"
    r"\b(?:like\s+being\s+(?:poor|broke|unprotected|unhealthy))\b|"
    r"\b(?:don'?t\s+care\s+about\s+(?:my\s+)?(?:health|safety|protection|savings|money|family))\b|"
    r"\b(?:don'?t\s+want\s+(?:to\s+save|discounts|free\s+rewards|savings|money))\b|"
    r"\b(?:miss\s+out\s+on\s+savings|pay\s+regular\s+price|rather\s+pay\s+more)\b|"
    r"\b(?:no\s+thanks[,\s]+(?:i|we)\s+(?:hate|prefer|don'?t|refuse|like))\b"
    r")",
    re.IGNORECASE,
)

# 3. Hidden Fee Disclaimer Regex (word-boundary guarded against false positives like 'coffee')
RE_FEE_DISCLAIMER = re.compile(
    r"\b(?:fee|fees|processing\s+fee|handling\s+fee|surcharge|service\s+fee|destination\s+fee|resort\s+fee|mandatory|additional\s+fee|non-refundable\s+fee|per\s+month\s+after)\b",
    re.IGNORECASE,
)

# -----------------------------------------------------------------------------
# Register spaCy Matcher Rules
# -----------------------------------------------------------------------------
matcher.add(
    "SPACY_FALSE_URGENCY",
    [
        [
            {"LOWER": {"IN": ["only", "just"]}},
            {"LIKE_NUM": True},
            {"LOWER": {"IN": ["left", "remaining", "available", "rooms", "items", "seats", "tickets", "copies"]}},
        ],
        [
            {"LOWER": {"IN": ["offer", "deal", "discount", "sale"]}},
            {"LOWER": {"IN": ["expires", "ends", "closing"]}},
        ],
        [
            {"LOWER": {"IN": ["hurry", "rush", "act"]}},
            {"LOWER": {"IN": ["now", "fast", "today"]}},
        ],
    ],
)

matcher.add(
    "SPACY_CONFIRM_SHAMING",
    [
        [
            {"LOWER": "i"},
            {"LOWER": {"IN": ["hate", "loathe", "dislike"]}},
            {"LOWER": {"IN": ["saving", "savings", "discounts", "money", "deals", "gifts", "rewards"]}},
        ],
        [
            {"LOWER": {"IN": ["prefer", "rather"]}},
            {"LOWER": {"IN": ["paying", "to", "pay"]}},
            {"LOWER": {"IN": ["full", "more", "regular"]}},
            {"LOWER": {"IN": ["price", "cost", "amount", "rate"]}},
        ],
        [
            {"LOWER": "no"},
            {"IS_PUNCT": True, "OP": "?"},
            {"LOWER": "thanks", "OP": "?"},
            {"IS_PUNCT": True, "OP": "?"},
            {"LOWER": "i"},
            {"LOWER": {"IN": ["hate", "loathe", "prefer", "dont", "don't"]}},
        ],
    ],
)


# -----------------------------------------------------------------------------
# NLP Matching Functions
# -----------------------------------------------------------------------------
def match_false_urgency(text: str) -> Optional[Dict[str, Any]]:
    """
    Evaluates whether text contains false urgency or countdown timer patterns
    using compiled regex and spaCy matching rules.
    """
    clean_text = text.strip()
    if not clean_text or len(clean_text) < 3:
        return None

    # 1. Regex countdown check
    clock_match = RE_COUNTDOWN_TIME.search(clean_text)
    if clock_match:
        return {
            "matched": True,
            "type": "false_urgency",
            "subtype": "countdown",
            "matched_text": clock_match.group(0),
            "full_text": clean_text,
            "confidence": 0.95,
            "severity": "high",
        }

    # 2. Regex stock limits & urgency phrases
    urgency_match = RE_FALSE_URGENCY_PATTERNS.search(clean_text)
    if urgency_match:
        return {
            "matched": True,
            "type": "false_urgency",
            "subtype": "scarcity",
            "matched_text": urgency_match.group(0),
            "full_text": clean_text,
            "confidence": 0.92,
            "severity": "high",
        }

    # 3. spaCy token matcher
    doc = nlp(clean_text)
    matches = matcher(doc)
    for match_id, start, end in matches:
        rule_name = nlp.vocab.strings[match_id]
        if rule_name == "SPACY_FALSE_URGENCY":
            span = doc[start:end]
            return {
                "matched": True,
                "type": "false_urgency",
                "subtype": "token_pattern",
                "matched_text": span.text,
                "full_text": clean_text,
                "confidence": 0.90,
                "severity": "high",
            }

    return None


def match_confirm_shaming(text: str) -> Optional[Dict[str, Any]]:
    """
    Evaluates whether decline copy contains confirm-shaming manipulative guilt
    using compiled regex and spaCy linguistic analysis.
    """
    clean_text = text.strip()
    if not clean_text or len(clean_text) < 4:
        return None

    # 1. Regex confirm-shaming
    shame_match = RE_CONFIRM_SHAMING_PATTERNS.search(clean_text)
    if shame_match:
        return {
            "matched": True,
            "type": "confirm_shaming",
            "matched_text": clean_text,
            "keyword": shame_match.group(0),
            "replacement_text": "No, thanks",
            "confidence": 0.96,
            "severity": "high",
        }

    # 2. spaCy matcher & dependency parsing
    doc = nlp(clean_text)
    matches = matcher(doc)
    for match_id, start, end in matches:
        rule_name = nlp.vocab.strings[match_id]
        if rule_name == "SPACY_CONFIRM_SHAMING":
            return {
                "matched": True,
                "type": "confirm_shaming",
                "matched_text": clean_text,
                "keyword": doc[start:end].text,
                "replacement_text": "No, thanks",
                "confidence": 0.94,
                "severity": "high",
            }

    # 3. Syntactic check: negation + negative emotion predicate
    lower = clean_text.lower()
    has_neg = any(tok.dep_ == "neg" or tok.lower_ in ["no", "nah", "never", "not"] for tok in doc)
    has_pejorative = any(w in lower for w in ["hate", "loathe", "prefer paying", "full price", "like being poor", "miss out"])
    if has_neg and has_pejorative:
        return {
            "matched": True,
            "type": "confirm_shaming",
            "matched_text": clean_text,
            "keyword": "syntactic_guilt",
            "replacement_text": "No, thanks",
            "confidence": 0.92,
            "severity": "high",
        }

    return None


# -----------------------------------------------------------------------------
# Contrast & Styling Perception Helpers
# -----------------------------------------------------------------------------
def parse_rgb(color_str: str) -> Optional[Tuple[float, float, float, float]]:
    if not color_str:
        return None
    color_str = color_str.strip().lower()

    if color_str.startswith("#"):
        hex_code = color_str.lstrip("#")
        if len(hex_code) == 3:
            hex_code = "".join([c * 2 for c in hex_code])
        if len(hex_code) == 6:
            r = int(hex_code[0:2], 16) / 255.0
            g = int(hex_code[2:4], 16) / 255.0
            b = int(hex_code[4:6], 16) / 255.0
            return (r, g, b, 1.0)

    match = re.match(r"rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)", color_str)
    if match:
        r = float(match.group(1)) / 255.0
        g = float(match.group(2)) / 255.0
        b = float(match.group(3)) / 255.0
        a = float(match.group(4)) if match.group(4) is not None else 1.0
        return (r, g, b, a)

    named_colors = {
        "transparent": (0.0, 0.0, 0.0, 0.0),
        "white": (1.0, 1.0, 1.0, 1.0),
        "black": (0.0, 0.0, 0.0, 1.0),
        "gray": (0.5, 0.5, 0.5, 1.0),
        "grey": (0.5, 0.5, 0.5, 1.0),
        "lightgray": (0.83, 0.83, 0.83, 1.0),
        "lightgrey": (0.83, 0.83, 0.83, 1.0),
    }
    return named_colors.get(color_str, None)


def srgb_to_linear(channel: float) -> float:
    if channel <= 0.04045:
        return channel / 12.92
    return math.pow((channel + 0.055) / 1.055, 2.4)


def relative_luminance(rgb: Tuple[float, float, float, float]) -> float:
    r_lin = srgb_to_linear(rgb[0])
    g_lin = srgb_to_linear(rgb[1])
    b_lin = srgb_to_linear(rgb[2])
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin


def calculate_contrast_ratio(fg_color: str, bg_color: str) -> float:
    fg = parse_rgb(fg_color) or (0.2, 0.2, 0.2, 1.0)
    bg = parse_rgb(bg_color) or (1.0, 1.0, 1.0, 1.0)
    if bg[3] == 0:
        bg = (1.0, 1.0, 1.0, 1.0)

    if fg[3] < 1.0:
        alpha = fg[3]
        fg = (
            fg[0] * alpha + bg[0] * (1 - alpha),
            fg[1] * alpha + bg[1] * (1 - alpha),
            fg[2] * alpha + bg[2] * (1 - alpha),
            1.0,
        )

    l1 = relative_luminance(fg)
    l2 = relative_luminance(bg)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return round((lighter + 0.05) / (darker + 0.05), 2)


def parse_inline_style(style_attr: Optional[str]) -> Dict[str, str]:
    if not style_attr:
        return {}
    styles = {}
    for part in style_attr.split(";"):
        if ":" in part:
            k, v = part.split(":", 1)
            styles[k.strip().lower()] = v.strip().lower()
    return styles


def extract_monetary_values(text: str) -> List[float]:
    matches = re.findall(r"(?:[\$\€\£]\s*|usd\s*|eur\s*)?(\d+(?:\.\d{2})?)\s*(?:[\$\€\£]|usd|eur)?", text, re.IGNORECASE)
    values = []
    for m in matches:
        try:
            val = float(m)
            if val > 0:
                values.append(val)
        except ValueError:
            pass
    return values


# Pre-checked add-on sensitivity keywords
SENSITIVE_OPT_IN_KEYWORDS = [
    "newsletter",
    "marketing",
    "partner",
    "offers",
    "promotion",
    "promotional",
    "insurance",
    "warranty",
    "protection",
    "donation",
    "tip",
    "subscribe",
    "subscription",
    "recurring",
    "updates",
    "share my data",
    "priority shipping",
    "rush processing",
    "add-on",
    "service plan",
]

FEE_DISCLAIMER_KEYWORDS = [
    "fee",
    "fees",
    "processing",
    "handling",
    "surcharge",
    "service fee",
    "destination fee",
    "resort fee",
    "mandatory",
    "additional",
    "non-refundable",
    "plus tax",
    "taxes and fees",
    "per month after",
]

OPTOUT_KEYWORDS = [
    "no",
    "cancel",
    "decline",
    "skip",
    "opt-out",
    "opt out",
    "reject",
    "not now",
    "never mind",
    "dismiss",
    "close",
    "unsubscribe",
    "hate",
    "full price",
]
