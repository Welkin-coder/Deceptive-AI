# Real-Time Deceptive UI/UX Detection and Remediation Engine

A production-grade, local, open-source AI engine that identifies, classifies, and automatically remediates deceptive web design patterns (dark patterns, manipulinks, drip pricing, and psychological coercion) using **FastAPI**, **spaCy** (`en_core_web_sm`), **BeautifulSoup4**, and **Playwright**.

---

## 🏛️ System Architecture

```
                      ┌──────────────────────────────────────────────┐
                      │             Web Browser Client               │
                      │  (content_script.js / Extension / Script)    │
                      └──────────────┬───────────────────────────────┘
                                     │
                 POST /scan/url      │     JSON Remediation Directives
                 POST /scan/text     ▼     (Unchecks, Overlays, Overrides)
                      ┌──────────────────────────────────────────────┐
                      │              FastAPI Backend                 │
                      │   - Async Exception Handlers (504, 502, 400) │
                      │   - CORS: chrome-extension://* & localhost   │
                      │   - In-Memory LRU Cache (15-min TTL)         │
                      └──────┬───────────────────────────────┬───────┘
                             │                               │
                             ▼                               ▼
       ┌───────────────────────────────┐   ┌───────────────────────────────┐
       │     Playwright + BS4 Engine   │   │       spaCy NLP Auditor       │
       │  - Live DOM Tree Extraction   │   │  - Linguistic Pattern Matcher │
       │  - Computed Style Perception  │   │  - Dependency Syntax Parser   │
       │  - WCAG 2.1 Contrast Math     │   │  - Emotional Valency Analysis │
       │  - Coordinate Bounding Rects  │   │  - False Urgency Scarcity     │
       └───────────────────────────────┘   └───────────────────────────────┘
```

---

## 📁 Project Structure

```
deceptive-ui-detector/
├── backend/
│   ├── cache.py                  # Thread-safe in-memory LRU Cache with 15-minute TTL
│   ├── config.py                 # Thresholds, viewport geometry & deception scoring weights
│   ├── main.py                   # FastAPI server with async exception handlers, CORS & caching
│   ├── dom/
│   │   ├── rules.py              # WCAG 2.1 contrast math, style parsers & keyword taxonomies
│   │   └── scanner.py            # DOMScanner implementing the 4 core pattern categories
│   ├── nlp/
│   │   └── auditor.py            # spaCy token matcher & syntactic confirm-shaming auditor
│   ├── schemas/
│   │   └── models.py             # Pydantic data contracts (Finding, Report, ErrorResponse)
│   └── tests/
│       ├── test_api.py           # Integration tests for routes, caching, CORS, & error handlers
│       ├── test_dom.py           # Contrast math & heuristic tests
│       ├── test_nlp.py           # spaCy manipulative language unit tests
│       └── test_scanner.py       # Detection accuracy tests against mock HTML snippets
├── frontend/
│   ├── content_script.js         # Browser remediation script (unchecking, warning overlays)
│   ├── remediation.js            # Standalone HUD and highlight utility
│   ├── extension/
│   │   ├── manifest.json         # Chrome/Edge Manifest V3 extension definition
│   │   ├── popup.html            # Extension popup user interface
│   │   ├── popup.js              # Extension trigger logic
│   │   └── content_script.js     # Extension bridge content script
│   └── demo/
│       ├── demo_store.html       # Full e-commerce harness with authentic dark patterns
│       └── demo_styles.css       # Layout & deceptive visual asymmetry styling
├── requirements.txt              # Production Python package dependencies
└── README.md                     # Engineering documentation and quickstart
```

---

## 🎯 The Four Core Deceptive Pattern Categories

| Category | UI / Linguistic Mechanism | Detection Heuristic in `scanner.py` | Client-Side Remediation (`content_script.js`) |
| :--- | :--- | :--- | :--- |
| ⏳ **False Urgency** | Countdown clocks, artificial stock limits, pressure banners | Regex `\b(?:\d{1,2}:){1,2}\d{2}\b`, timer tags (`.countdown`, `[data-timer]`), and spaCy scarcity tokens (`"only \d+ left in stock"`, `"\d+ people viewing"`) | Overlays high-visibility warning banner directly over timer and freezes ticking interval |
| 🙈 **Confirm-Shaming** | Emotionally manipulative decline buttons and manipulinks | Interactive element copy parsed via spaCy dependency syntax for negation + self-deprecating predicates (*"No thanks, I hate saving money"*, *"I prefer paying full price"*) | Rewrites toxic guilt-trip copy to neutral, objective refusal (*"No, thanks"*) |
| 📦 **Hidden Costs** | Pre-checked add-on boxes (insurance, warranty) & mismatched price totals | DOM traversal detecting `input[type="checkbox"]:checked` with commercial keywords, plus comparison of subtotal vs grand total or fine-print surcharge disclaimers | Automatically unchecks sneaky add-on inputs and elevates concealed fees into bold alert blocks |
| 👁️ **Visual Disguise** | Low-contrast decline buttons, tiny text (<11px), hidden opt-outs | Computes WCAG 2.1 relative luminance contrast (<3.0:1), reduced opacity (<0.65), and hidden styles (`display: none`, `visibility: hidden`) on opt-out options | Injects CSS overrides to restore full opacity, legible font size, high-contrast borders, and prominence |

---

## ⚡ Robustness, Caching & Security Features

### 1. Asynchronous Exception Handlers
`backend/main.py` handles runtime failures asynchronously:
- **`PlaywrightTimeoutError` / `asyncio.TimeoutError`**: Returns HTTP `504 Gateway Timeout` with structured `ErrorResponse`.
- **`InvalidURLError`**: Validates schemes (`http`, `https`, `file`), malformed URLs, and unresolvable hostnames, returning HTTP `400 Bad Request`.
- **`NetworkFailureError`**: Catches DNS resolution failures (`ERR_NAME_NOT_RESOLVED`), connection refused (`ERR_CONNECTION_REFUSED`), returning HTTP `502 Bad Gateway`.

### 2. 15-Minute In-Memory LRU Cache
`backend/cache.py` provides thread-safe caching with a 15-minute (900 seconds) Time-To-Live:
- Avoids redundant Playwright browser compute for repeated audits.
- Injects HTTP response header: `X-Cache: HIT` or `X-Cache: MISS`.
- Populates `cached: true` and `cache_age_seconds` in the `ScanReport` JSON.
- Cache telemetry endpoint: `GET /cache/stats`.
- Cache flush endpoint: `POST /cache/clear`.

### 3. Restricted CORS Middleware
FastAPI CORS middleware is strictly restricted to:
- Local browser extensions: `allow_origin_regex=r"^chrome-extension://[a-z0-9]+$"`
- Local dashboard development: `http://localhost:*` and `http://127.0.0.1:*`

---

## 🧪 Testing Suite Execution

Run all 22 unit, integration, and mock HTML tests:
```bash
pytest backend/tests -v
```

Output:
```
backend/tests/test_api.py::test_health_check_endpoint PASSED             [  4%]
backend/tests/test_api.py::test_scan_text_endpoint_and_caching PASSED    [  9%]
backend/tests/test_api.py::test_scan_local_file_url PASSED               [ 13%]
backend/tests/test_api.py::test_invalid_url_exception_handling PASSED    [ 18%]
backend/tests/test_api.py::test_cors_middleware_allowed_for_extensions_and_localhost PASSED [ 22%]
backend/tests/test_api.py::test_cache_telemetry_and_clear_endpoints PASSED [ 27%]
backend/tests/test_dom.py::test_contrast_ratio_calculation PASSED        [ 31%]
backend/tests/test_dom.py::test_parse_rgb_formats PASSED                 [ 36%]
backend/tests/test_dom.py::test_sensitive_opt_in_keywords PASSED         [ 40%]
backend/tests/test_dom.py::test_fee_disclaimer_keywords PASSED           [ 45%]
backend/tests/test_nlp.py::test_false_urgency_detection PASSED           [ 50%]
backend/tests/test_nlp.py::test_confirm_shaming_detection PASSED         [ 54%]
backend/tests/test_nlp.py::test_hidden_fees_language PASSED              [ 59%]
backend/tests/test_nlp.py::test_forced_continuity_language PASSED        [ 63%]
backend/tests/test_nlp.py::test_trick_question_double_negative PASSED    [ 68%]
backend/tests/test_nlp.py::test_benign_text_produces_no_false_positives PASSED [ 72%]
backend/tests/test_scanner.py::test_false_urgency_countdown_and_stock_limits PASSED [ 77%]
backend/tests/test_scanner.py::test_confirm_shaming_classification PASSED [ 81%]
backend/tests/test_scanner.py::test_hidden_costs_prechecked_addon_boxes PASSED [ 86%]
backend/tests/test_scanner.py::test_hidden_costs_price_mismatch_and_drip_fees PASSED [ 90%]
backend/tests/test_scanner.py::test_visual_disguise_low_contrast_and_hidden_optout PASSED [ 95%]
backend/tests/test_scanner.py::test_benign_html_clean_baseline PASSED    [100%]

============================= 22 passed in 3.72s ==============================
```

---

## 🚀 Running the Server & Demo

```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```
Open [http://127.0.0.1:8000/demo/page](http://127.0.0.1:8000/demo/page) in your browser to experience live real-time detection, floating warning overlays, and one-click auto-remediation!
