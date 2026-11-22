"""
FastAPI application for Real-Time Deceptive UI/UX Detection and Remediation Engine.
Includes:
- CORSMiddleware allowing all origins (*) for Chrome extensions and web clients.
- Hardened endpoints with async try/except blocks returning standard HTTP 500 errors.
- 5-minute in-memory LRU cache hashing incoming HTML/text payloads.
"""

from __future__ import annotations
import time
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional
from urllib.parse import urlparse
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from playwright.async_api import TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError

from backend.config import settings
from backend.schemas.models import (
    UrlScanRequest,
    TextScanRequest,
    ScanReport,
    PatternFinding,
    RemediationDirective,
    ErrorResponse,
)
from backend.nlp.auditor import NLPAuditor
from backend.dom.scanner import DOMScanner
from backend.cache import scan_cache


class InvalidURLError(Exception):
    """Raised when target URL has invalid scheme, format, or missing hostname."""
    pass


# Global singleton instances
nlp_auditor: NLPAuditor | None = None
dom_scanner: DOMScanner | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes NLP models, DOM scanner, and cache on startup."""
    global nlp_auditor, dom_scanner
    print(f"[*] Preloading spaCy NLP model: {settings.SPACY_MODEL}...")
    nlp_auditor = NLPAuditor(settings.SPACY_MODEL)
    dom_scanner = DOMScanner(nlp_auditor=nlp_auditor)
    print("[+] Deceptive UI/UX Detection Engine initialized and ready.")
    yield
    print("[-] Shutting down Deceptive UI/UX Detection Engine.")


# 1. Initialize FastAPI app FIRST 🚀
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Production-ready autonomous detection and remediation API for deceptive design patterns.",
    lifespan=lifespan,
)

# 2. Add CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Cache", "X-Execution-Time-Ms"],
)

# 3. Mount static files AFTER app is created 📂
BASE_DIR = Path(__file__).resolve().parent.parent   # -> project root
DEMO_DIR = BASE_DIR / "frontend" / "demo"

if DEMO_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(DEMO_DIR)), name="static")
else:
    print(f"[!] Warning: demo directory not found at {DEMO_DIR}; skipping /static mount.")


def get_nlp_auditor() -> NLPAuditor:
    global nlp_auditor
    if nlp_auditor is None:
        nlp_auditor = NLPAuditor(settings.SPACY_MODEL)
    return nlp_auditor


def get_dom_scanner() -> DOMScanner:
    global dom_scanner
    if dom_scanner is None:
        dom_scanner = DOMScanner(nlp_auditor=get_nlp_auditor())
    return dom_scanner


def validate_and_normalize_url(url: Optional[str]) -> str:
    """Validates URL string and normalizes protocol."""
    if not url:
        raise InvalidURLError("URL string cannot be empty.")
    cleaned = url.strip()
    if not cleaned:
        raise InvalidURLError("URL string cannot be empty.")

    if cleaned.startswith("file://"):
        return cleaned

    if "://" not in cleaned:
        cleaned = f"https://{cleaned}"

    parsed = urlparse(cleaned)
    if parsed.scheme not in ("http", "https", "file"):
        raise InvalidURLError(f"Unsupported URL scheme '{parsed.scheme}'. Only http, https, and file are permitted.")

    if parsed.scheme in ("http", "https"):
        if not parsed.netloc or ("." not in parsed.netloc and parsed.netloc not in ("localhost", "127.0.0.1")):
            raise InvalidURLError(f"Invalid host or domain name in URL '{url}'.")

    return cleaned


# -----------------------------------------------------------------------------
# API Endpoints
# -----------------------------------------------------------------------------

@app.get("/", tags=["System"])
async def root():
    return {
        "status": "online",
        "message": "Deceptive UI/UX Detection Engine is running",
        "docs": "/docs",
        "health": "/health",
    }
    
@app.get("/health", tags=["System"])
async def health_check() -> Dict[str, Any]:
    """Returns engine health status, NLP model state, and cache statistics."""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "spacy_model": settings.SPACY_MODEL,
        "playwright_enabled": True,
        "cache": scan_cache.stats(),
    }


@app.post(
    "/scan/url",
    response_model=ScanReport,
    tags=["Auditing"],
    summary="Scan web page URL or raw client HTML for deceptive DOM patterns",
)
async def scan_url(request: UrlScanRequest, response: Response) -> ScanReport:
    """
    Scans a web page URL or raw HTML extracted by browser content script.
    - Caches results for 5 minutes based on payload hash to prevent redundant processing.
    - Hardened with async try/except blocks returning standard HTTP 500 errors.
    """
    try:
        raw_target = (request.html or request.url or "").strip()
        if not raw_target:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Must provide either 'url' or 'html' in request body.",
            )

        # 5-minute in-memory cache lookup
        cache_key = scan_cache.hash_content(raw_target)
        if not request.bypass_cache:
            cached_report = scan_cache.get(cache_key)
            if cached_report is not None:
                response.headers["X-Cache"] = "HIT"
                return cached_report

        response.headers["X-Cache"] = "MISS"
        scanner = get_dom_scanner()

        # If raw HTML was extracted directly by Chrome extension content_script.js
        if request.html:
            report = scanner.scan_html(request.html, target=request.url or "client_dom")
        else:
            norm_url = validate_and_normalize_url(request.url)
            report = await scanner.scan_url(
                url=norm_url,
                timeout_ms=request.timeout_ms,
                wait_for_network_idle=request.wait_for_network_idle,
            )

        # Store in 5-minute LRU cache
        scan_cache.set(cache_key, report, ttl_seconds=300.0)
        return report

    except HTTPException:
        raise
    except InvalidURLError as iue:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "InvalidURLError", "message": str(iue), "detail": str(iue), "status_code": 400},
        )
    except PlaywrightTimeoutError as pte:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Navigation timed out: {str(pte)}",
        )
    except Exception as exc:
        # Standard HTTP 500 error instead of crashing
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"DOM audit failed: {str(exc)}",
        )


@app.post(
    "/scan/text",
    response_model=ScanReport,
    tags=["Auditing"],
    summary="Scan raw text copy for manipulative language and confirm-shaming",
)
async def scan_text(request: TextScanRequest, response: Response) -> ScanReport:
    """
    Audits a raw text string, button label, or disclaimer using spaCy and regex.
    - Uses 5-minute in-memory LRU cache based on payload hash.
    - Hardened with async try/except blocks returning standard HTTP 500 errors.
    """
    try:
        text_clean = request.text.strip()
        if not text_clean:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Text input cannot be empty.")

        cache_key = scan_cache.hash_content(f"{text_clean}|{request.context}")
        if not request.bypass_cache:
            cached_report = scan_cache.get(cache_key)
            if cached_report is not None:
                response.headers["X-Cache"] = "HIT"
                return cached_report

        response.headers["X-Cache"] = "MISS"
        auditor = get_nlp_auditor()

        start_time = time.perf_counter()
        findings = auditor.analyze_text(
            text=text_clean,
            element_selector="text-target",
            context_hint=request.context or "generic",
        )

        raw_score = sum(settings.SEVERITY_WEIGHTS.get(f.severity.value, 5.0) for f in findings)
        risk_score = round(min(100.0, raw_score * 1.5), 1)

        if risk_score >= 60.0:
            risk_level = "SEVERE"
        elif risk_score >= 35.0:
            risk_level = "HIGH"
        elif risk_score >= 15.0:
            risk_level = "MODERATE"
        else:
            risk_level = "SAFE"

        by_category: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}
        directives: list[RemediationDirective] = []

        for f in findings:
            cat = f.type
            sev = f.severity.value
            by_category[cat] = by_category.get(cat, 0) + 1
            by_severity[sev] = by_severity.get(sev, 0) + 1
            directives.append(f.remediation)

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        report = ScanReport(
            target=text_clean[:100] + ("..." if len(text_clean) > 100 else ""),
            scan_type="text",
            page_title=None,
            risk_score=risk_score,
            risk_level=risk_level,
            total_findings=len(findings),
            findings_by_category=by_category,
            findings_by_severity=by_severity,
            findings=findings,
            remediation_directives=directives,
            execution_time_ms=elapsed_ms,
        )

        # Store in 5-minute cache
        scan_cache.set(cache_key, report, ttl_seconds=300.0)
        return report

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Text audit failed: {str(exc)}",
        )


@app.get("/cache/stats", tags=["System"])
async def get_cache_stats() -> Dict[str, Any]:
    """Returns telemetry on in-memory LRU cache."""
    return scan_cache.stats()


@app.post("/cache/clear", tags=["System"])
async def clear_cache() -> Dict[str, str]:
    """Flushes the 5-minute in-memory scan cache."""
    scan_cache.clear()
    return {"message": "In-memory scan cache successfully cleared."}


@app.get("/demo/page", tags=["Demonstration"])
async def serve_demo_page():
    """Serves the interactive deceptive UI test harness."""
    demo_file = Path(__file__).resolve().parent.parent / "frontend" / "demo" / "demo_store.html"
    if demo_file.exists():
        return FileResponse(str(demo_file), media_type="text/html")
    return JSONResponse(
        status_code=404,
        content={"error": "Demo store HTML fixture not found on disk"},
    )
