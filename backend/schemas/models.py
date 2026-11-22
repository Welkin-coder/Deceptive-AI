"""
Data contracts and Pydantic schemas for the Deceptive UI/UX Detection and Remediation Engine.
Supports the four core dark pattern categories:
- ⏳ False Urgency
- 🙈 Confirm-Shaming
- 📦 Hidden Costs
- 👁️ Visual Disguise
"""

from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class DarkPatternCategory(str, Enum):
    # Core 4 Categories
    FALSE_URGENCY = "false_urgency"
    CONFIRM_SHAMING = "confirm_shaming"
    HIDDEN_COSTS = "hidden_costs"
    VISUAL_DISGUISE = "visual_disguise"

    # Backward-compatible aliases / sub-categories
    PRECHECKED_BOX = "prechecked_box"
    OBSCURED_ACTION = "obscured_action"
    HIDDEN_FEES = "hidden_fees"
    FORCED_CONTINUITY = "forced_continuity"
    SNEAK_INTO_BASKET = "sneak_into_basket"
    TRICK_QUESTIONS = "trick_questions"


class SeverityLevel(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RemediationActionType(str, Enum):
    UNCHECK = "uncheck"
    RESTORE_CONTRAST = "restore_contrast"
    NEUTRALIZE_TEXT = "neutralize_text"
    EXPOSE_HIDDEN_FEE = "expose_hidden_fee"
    FREEZE_COUNTDOWN = "freeze_countdown"
    ALERT_BOX = "alert_box"


class RemediationDirective(BaseModel):
    action: RemediationActionType = Field(..., description="Actionable remediation type")
    target_selector: str = Field(..., description="CSS selector identifying target DOM element")
    replacement_text: Optional[str] = Field(None, description="Neutral replacement text if applicable")
    css_overrides: Optional[Dict[str, str]] = Field(default_factory=dict, description="Style fixes to restore visibility or contrast")
    explanation: str = Field(..., description="Human-readable remediation reason")


class BoundingBox(BaseModel):
    x: float = Field(..., description="X coordinate in viewport")
    y: float = Field(..., description="Y coordinate in viewport")
    width: float = Field(..., description="Element width in pixels")
    height: float = Field(..., description="Element height in pixels")


class PatternFinding(BaseModel):
    id: str = Field(..., description="Unique deterministic identifier for the finding")
    type: str = Field(default="dark_pattern", description="Taxonomy classification type (false_urgency, confirm_shaming, hidden_costs, etc.)")
    category: DarkPatternCategory = Field(..., description="Taxonomy classification of the dark pattern")
    pattern_name: str = Field(..., description="Human-readable pattern title")
    severity: SeverityLevel = Field(..., description="Severity rating")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence between 0.0 and 1.0")
    selector: str = Field(..., description="CSS selector for the deceptive element")
    tag_name: Optional[str] = Field(None, description="HTML tag name (e.g., input, button, a)")
    attributes: Dict[str, str] = Field(default_factory=dict, description="Relevant HTML element attributes")
    bounding_box: Optional[BoundingBox] = Field(None, description="Viewport coordinates and dimensions")
    matched_text: str = Field(default="", description="Flagged text or attribute snippet")
    deceptive_text: str = Field(default="", description="Flagged text or attribute snippet")
    explanation: str = Field(..., description="Detailed audit explanation of why this constitutes deceptive UI/UX")
    remediation: RemediationDirective = Field(..., description="Concrete client-side remediation instructions")

    @classmethod
    def model_validate(cls, obj: Any, *args, **kwargs):
        if isinstance(obj, dict):
            if "type" not in obj and "category" in obj:
                cat = obj["category"]
                obj["type"] = cat.value if hasattr(cat, "value") else str(cat)
            if not obj.get("matched_text") and obj.get("deceptive_text"):
                obj["matched_text"] = obj["deceptive_text"]
            elif not obj.get("deceptive_text") and obj.get("matched_text"):
                obj["deceptive_text"] = obj["matched_text"]
        return super().model_validate(obj, *args, **kwargs)


class UrlScanRequest(BaseModel):
    url: Optional[str] = Field(None, description="Target web page URL to inspect")
    html: Optional[str] = Field(None, description="Direct DOM HTML string extracted by browser content script")
    timeout_ms: int = Field(default=30000, ge=1000, le=90000, description="Playwright navigation timeout in milliseconds")
    wait_for_network_idle: bool = Field(default=False, description="Whether to wait for networkidle state")
    bypass_cache: bool = Field(default=False, description="Bypass 5-minute in-memory cache and force live scan")


class TextScanRequest(BaseModel):
    text: str = Field(..., min_length=2, max_length=50000, description="Raw text snippet, copy, or button label to audit")
    context: Optional[str] = Field(default="generic", description="UI context hint: button, modal, disclaimer, alert, or generic")
    bypass_cache: bool = Field(default=False, description="Bypass 5-minute in-memory cache")


class ScanReport(BaseModel):
    target: str = Field(..., description="URL or input text audited")
    scan_type: str = Field(..., description="'url', 'text', or 'mock_html'")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="ISO-8601 audit timestamp")
    page_title: Optional[str] = Field(None, description="Scanned page title if URL scan")
    risk_score: float = Field(..., ge=0.0, le=100.0, description="Computed Deception Risk Score from 0 (clean) to 100 (hostile)")
    risk_level: str = Field(..., description="Overall risk rating: SAFE, MODERATE, HIGH, or SEVERE")
    total_findings: int = Field(..., description="Total count of dark patterns flagged")
    findings_by_category: Dict[str, int] = Field(default_factory=dict, description="Finding counts grouped by taxonomy category")
    findings_by_severity: Dict[str, int] = Field(default_factory=dict, description="Finding counts grouped by severity level")
    findings: List[PatternFinding] = Field(default_factory=list, description="Detailed list of detected deceptive elements")
    remediation_directives: List[RemediationDirective] = Field(default_factory=list, description="Array of executable remediation directives")
    execution_time_ms: float = Field(..., description="Total audit execution duration in milliseconds")
    cached: bool = Field(default=False, description="Whether this report was returned from the 5-minute in-memory LRU cache")
    cache_age_seconds: Optional[float] = Field(None, description="Elapsed time in seconds since this scan result was cached")


class ErrorResponse(BaseModel):
    error: str = Field(..., description="Standardized error category name")
    message: str = Field(..., description="Human-readable error description")
    detail: Optional[str] = Field(None, description="Underlying exception or failure detail")
    status_code: int = Field(..., description="HTTP status code")
