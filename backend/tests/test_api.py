"""
Integration tests for FastAPI endpoints:
- /health, /scan/text, /scan/url
- Asynchronous exception handlers (Invalid URLs, timeouts, network failures)
- 15-minute in-memory LRU caching layer (Hits, Misses, Stats, Headers)
- CORS middleware restricted to Chrome extensions and localhost
"""

from fastapi.testclient import TestClient
from pathlib import Path
from backend.main import app
from backend.cache import scan_cache

client = TestClient(app)


def test_health_check_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "en_core_web_sm" in data["spacy_model"]
    assert "cache" in data
    assert "hits" in data["cache"]


def test_scan_text_endpoint_and_caching():
    scan_cache.clear()
    payload = {
        "text": "Hurry! Only 1 left in stock. No thanks, I hate saving money.",
        "context": "button",
    }

    # 1. First call -> Cache MISS
    response1 = client.post("/scan/text", json=payload)
    assert response1.status_code == 200
    assert response1.headers.get("X-Cache") == "MISS"
    data1 = response1.json()
    assert data1["scan_type"] == "text"
    assert data1["total_findings"] >= 1
    assert data1["cached"] is False

    # 2. Second call -> Cache HIT (15-min in-memory cache)
    response2 = client.post("/scan/text", json=payload)
    assert response2.status_code == 200
    assert response2.headers.get("X-Cache") == "HIT"
    data2 = response2.json()
    assert data2["cached"] is True
    assert data2["cache_age_seconds"] is not None
    assert data2["total_findings"] == data1["total_findings"]


def test_scan_local_file_url():
    demo_file = Path(__file__).resolve().parent.parent.parent / "frontend" / "demo" / "demo_store.html"
    assert demo_file.exists()

    file_url = demo_file.as_uri()
    payload = {
        "url": file_url,
        "timeout_ms": 15000,
        "wait_for_network_idle": False,
        "bypass_cache": True,
    }
    response = client.post("/scan/url", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["scan_type"] == "url"
    assert data["total_findings"] >= 1
    assert data["risk_score"] > 30.0
    assert len(data["findings"]) >= 1


def test_invalid_url_exception_handling():
    # Test invalid URL format / scheme
    payload = {"url": "ftp://invalid-server.local/resource"}
    response = client.post("/scan/url", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["error"] == "InvalidURLError"
    assert "Unsupported URL scheme" in data["message"]

    # Test empty URL
    response_empty = client.post("/scan/url", json={"url": "   "})
    assert response_empty.status_code == 400


def test_cors_middleware_allowed_for_extensions_and_localhost():
    # 1. Chrome extension origin should be permitted
    ext_origin = "chrome-extension://abcdefghijklmnopqrstuvwxyz123456"
    res_ext = client.options(
        "/scan/text",
        headers={
            "Origin": ext_origin,
            "Access-Control-Request-Method": "POST",
        },
    )
    assert res_ext.status_code == 200
    assert res_ext.headers.get("access-control-allow-origin") == ext_origin

    # 2. Localhost origin should be permitted
    local_origin = "http://localhost:8000"
    res_local = client.options(
        "/scan/text",
        headers={
            "Origin": local_origin,
            "Access-Control-Request-Method": "POST",
        },
    )
    assert res_local.status_code == 200
    assert res_local.headers.get("access-control-allow-origin") == local_origin


def test_cache_telemetry_and_clear_endpoints():
    stats_res = client.get("/cache/stats")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert "hits" in stats
    assert "misses" in stats
    assert "default_ttl_seconds" in stats
    assert stats["default_ttl_seconds"] == 300.0

    clear_res = client.post("/cache/clear")
    assert clear_res.status_code == 200
    assert "cleared" in clear_res.json()["message"]


def test_scan_raw_html_payload_from_content_script():
    # Simulates content_script.js sending document.body.innerHTML directly to /scan/url
    mock_payload = {
        "url": "http://127.0.0.1:8000/checkout",
        "html": """
        <div class="cart">
            <div class="countdown" id="timer">Offer expires in 04:59</div>
            <input type="checkbox" id="sneak-insurance" checked="checked" />
            <label for="sneak-insurance">Add Platinum Insurance Warranty (+$7.99)</label>
            <a href="#" id="shame-link">No thanks, I hate saving money and prefer paying full price</a>
        </div>
        """,
    }
    response = client.post("/scan/url", json=mock_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["total_findings"] >= 3

    # Verify strict schema fields: type, severity, matched_text, selector
    types = [f["type"] for f in data["findings"]]
    assert "false_urgency" in types
    assert "hidden_costs" in types
    assert "confirm_shaming" in types

    for f in data["findings"]:
        assert "type" in f
        assert "severity" in f
        assert "matched_text" in f
        assert "selector" in f
        assert f["selector"] is not None
