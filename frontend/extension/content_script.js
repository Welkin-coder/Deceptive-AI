/**
 * Real-Time Deceptive UI/UX Detection and Remediation Engine
 * Browser Content Script (frontend/extension/content_script.js)
 *
 * Listens for manual scan triggers from the extension popup (START_SCAN / SCAN_PAGE),
 * extracts the live DOM HTML, delegates the API request to the background service worker
 * via chrome.runtime.sendMessage({ action: "PROCESS_DOM" }) to bypass Mixed Content restrictions,
 * and executes client-side remediation upon receiving the detection report.
 */

(function () {
    'use strict';

    let lastFindings = [];

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    /**
     * Resolves a DOM element safely using CSS selector or element ID fallback.
     */
    function resolveElement(selector) {
        if (!selector) return null;
        try {
            const el = document.querySelector(selector);
            if (el) return el;
        } catch (e) {
            // Ignored, proceed to ID fallback
        }

        if (selector.startsWith('#')) {
            const byId = document.getElementById(selector.slice(1));
            if (byId) return byId;
        }

        return null;
    }

    /**
     * Iterates through detected patterns and applies active DOM remediation.
     */
    function remediatePage(findings) {
        if (!Array.isArray(findings) || findings.length === 0) {
            console.log('[Deceptive UI Shield] No dark patterns detected.');
            return;
        }

        console.log(`[Deceptive UI Shield] Remediating ${findings.length} detected patterns...`);
        lastFindings = findings;

        findings.forEach((item) => {
            const selector = item.selector || item.remediation?.target_selector;
            const element = resolveElement(selector);
            if (!element) return;

            const patternType = (item.type || item.category || '').toLowerCase();
            const matchedText = item.matched_text || item.deceptive_text || '';
            const findingId = item.id || Math.random().toString(36).substring(2, 9);

            // 1. Hidden / Pre-Checked Add-on Boxes -> Uncheck & dispatch change events
            if (
                patternType === 'hidden_costs' ||
                patternType === 'prechecked_box' ||
                (element.tagName.toLowerCase() === 'input' && (element.type === 'checkbox' || element.type === 'radio'))
            ) {
                if (element.checked) {
                    element.checked = false;
                    element.dispatchEvent(new Event('change', { bubbles: true }));
                    element.dispatchEvent(new Event('input', { bubbles: true }));
                    console.log(`[Deceptive UI Shield] Unchecked deceptive add-on: ${selector}`);

                    // Add green neutralized indicator badge
                    if (!element.parentNode.querySelector(`.dark-pattern-uncheck[data-for="${findingId}"]`)) {
                        const uncheckNotice = document.createElement('div');
                        uncheckNotice.className = 'dark-pattern-warning dark-pattern-uncheck';
                        uncheckNotice.dataset.for = findingId;
                        uncheckNotice.style.cssText = `
                            display: inline-block;
                            background-color: #ecfdf5;
                            color: #065f46;
                            border: 1px solid #10b981;
                            border-radius: 4px;
                            padding: 3px 8px;
                            font-size: 11px;
                            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                            font-weight: 600;
                            margin: 4px 0;
                            vertical-align: middle;
                        `;
                        uncheckNotice.innerHTML = `🛡️ <b>Pre-checked add-on neutralized:</b> "${escapeHtml(matchedText)}"`;
                        element.parentNode.insertBefore(uncheckNotice, element.nextSibling);
                    }
                }
            }

            // 2. False Urgency or Confirm-Shaming -> High-visibility red border & warning badge
            if (patternType === 'false_urgency' || patternType === 'confirm_shaming') {
                // High-visibility CSS border & outline
                element.style.outline = '3px solid red';
                element.style.border = '3px solid red';

                // Freeze artificial countdown clocks
                if (patternType === 'false_urgency') {
                    element.dataset.frozen = 'true';
                }

                // Neutralize confirm-shaming copy if replacement text is available
                if (patternType === 'confirm_shaming' && item.remediation?.replacement_text) {
                    element.textContent = item.remediation.replacement_text;
                }

                // Insert warning badge next to element
                if (!element.parentNode.querySelector(`.dark-pattern-warning[data-for="${findingId}"]`)) {
                    const badge = document.createElement('div');
                    badge.className = 'dark-pattern-warning';
                    badge.dataset.for = findingId;
                    badge.style.cssText = `
                        display: inline-block;
                        background-color: #fef2f2;
                        color: #991b1b;
                        border: 2px solid #ef4444;
                        border-radius: 6px;
                        padding: 4px 8px;
                        font-size: 11px;
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                        font-weight: bold;
                        line-height: 1.3;
                        margin: 4px 0;
                        box-shadow: 0 2px 6px rgba(239, 68, 68, 0.2);
                        z-index: 999999;
                        vertical-align: middle;
                    `;
                    const label = patternType === 'false_urgency' ? 'FALSE URGENCY' : 'CONFIRM-SHAMING';
                    badge.innerHTML = `⚠️ <b>${label}:</b> ${escapeHtml(matchedText)}`;

                    if (element.nextSibling) {
                        element.parentNode.insertBefore(badge, element.nextSibling);
                    } else {
                        element.parentNode.appendChild(badge);
                    }
                }
            }

            // 3. Visual Disguise -> Restore accessible contrast and visibility
            if (patternType === 'visual_disguise' || patternType === 'obscured_action') {
                element.style.display = 'inline-block';
                element.style.visibility = 'visible';
                element.style.opacity = '1.0';
                element.style.color = '#111827';
                element.style.backgroundColor = '#e5e7eb';
                element.style.fontSize = '14px';
                element.style.fontWeight = '600';
                element.style.border = '2px solid #64748b';
                element.style.padding = '8px 16px';
                element.style.borderRadius = '6px';

                if (!element.parentNode.querySelector(`.dark-pattern-warning[data-for="${findingId}"]`)) {
                    const disguiseBadge = document.createElement('div');
                    disguiseBadge.className = 'dark-pattern-warning';
                    disguiseBadge.dataset.for = findingId;
                    disguiseBadge.style.cssText = `
                        display: inline-block;
                        background-color: #fffbeb;
                        color: #92400e;
                        border: 1px solid #f59e0b;
                        border-radius: 4px;
                        padding: 3px 6px;
                        font-size: 11px;
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                        font-weight: 600;
                        margin: 4px 0;
                    `;
                    disguiseBadge.innerHTML = `👁️ <b>Obscured Choice Restored:</b> "${escapeHtml(matchedText)}"`;
                    element.parentNode.insertBefore(disguiseBadge, element);
                }
            }
        });
    }

    /**
     * Executes scan by extracting HTML and dispatching PROCESS_DOM to background service worker.
     */
    function triggerScan(callback) {
        const pageHtml = document.body ? document.body.innerHTML : document.documentElement.innerHTML;
        const pageUrl = window.location.href;

        console.log('[Deceptive UI Shield] Dispatching PROCESS_DOM to background worker...');

        chrome.runtime.sendMessage(
            {
                action: 'PROCESS_DOM',
                payload: {
                    html: pageHtml,
                    url: pageUrl
                }
            },
            (response) => {
                if (chrome.runtime.lastError) {
                    console.error('[Deceptive UI Shield] Message error:', chrome.runtime.lastError.message);
                    if (callback) callback({ success: false, error: chrome.runtime.lastError.message });
                    return;
                }

                if (!response || response.error) {
                    console.warn('[Deceptive UI Shield] Scan error from backend:', response?.error);
                    if (callback) callback({ success: false, error: response?.error || 'Unknown backend error' });
                    return;
                }

                const findings = response.findings || response.items || [];
                remediatePage(findings);

                if (callback) {
                    callback({
                        success: true,
                        count: findings.length,
                        risk_score: response.risk_score,
                        risk_level: response.risk_level,
                        findings: findings
                    });
                }
            }
        );
    }

    // Message listener for popup manual triggers
    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
        if (request.action === 'START_SCAN' || request.action === 'SCAN_PAGE') {
            triggerScan((result) => {
                sendResponse(result);
            });
            // Keep message channel open for asynchronous response from background worker
            return true;
        }

        if (request.action === 'REMEDIATE_ALL') {
            remediatePage(lastFindings);
            sendResponse({ success: true, count: lastFindings.length });
            return true;
        }
    });

    // Expose utility on window for programmatic testing
    window.DeceptiveUIShield = {
        scan: () => new Promise((resolve, reject) => {
            triggerScan((result) => {
                if (result.success) resolve(result);
                else reject(new Error(result.error));
            });
        }),
        remediateAll: () => remediatePage(lastFindings)
    };
})();
