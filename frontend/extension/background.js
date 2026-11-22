/**
 * Real-Time Deceptive UI/UX Detection and Remediation Engine
 * Manifest V3 Background Service Worker (frontend/extension/background.js)
 *
 * Solves Chrome Mixed Content restrictions:
 * When an HTTPS webpage attempts to contact http://127.0.0.1:8000 directly from a content script,
 * modern browsers block it as mixed content. This background service worker runs in the extension's
 * background context with elevated host permissions, relaying DOM payloads to the local FastAPI backend.
 */

const API_ENDPOINT = 'http://127.0.0.1:8000/scan/url';

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'PROCESS_DOM') {
        const payload = request.payload || {};

        console.log('[Deceptive UI Shield: Background] Relaying DOM audit request to backend:', API_ENDPOINT);

        fetch(API_ENDPOINT, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        })
            .then(async (response) => {
                if (!response.ok) {
                    const errorText = await response.text();
                    throw new Error(`HTTP ${response.status}: ${errorText}`);
                }
                return response.json();
            })
            .then((data) => {
                console.log('[Deceptive UI Shield: Background] Received backend scan report:', data);
                sendResponse(data);
            })
            .catch((err) => {
                console.error('[Deceptive UI Shield: Background] Scan request failed:', err);
                sendResponse({
                    error: err.message,
                    findings: [],
                    remediation_directives: [],
                    total_findings: 0,
                    risk_score: 0.0,
                    risk_level: 'ERROR'
                });
            });

        // Return true to keep the message channel open for the asynchronous sendResponse
        return true;
    }
});
