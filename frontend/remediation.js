/**
 * Deceptive UI/UX Detection and Remediation Engine - Client-Side Script
 * 
 * Capabilities:
 * 1. Communicates with the FastAPI backend (/scan/url or local evaluation).
 * 2. Injects a non-destructive floating HUD / Control Center.
 * 3. Highlights deceptive elements with color-coded severity outlines and informative badges.
 * 4. Provides one-click inline and batch auto-remediation:
 *    - Unchecks sneaky opt-in checkboxes.
 *    - Neutralizes confirm-shaming copy to polite, objective refusals.
 *    - Restores contrast, opacity, and sizing on obscured cancel/decline buttons.
 *    - Exposes drip pricing & hidden fees right in the primary viewport.
 *    - Freezes psychological countdown clocks.
 */

(function () {
    'use strict';

    const CONFIG = {
        API_BASE_URL: 'http://localhost:8000',
        AUTO_SCAN: true,
        SCAN_TIMEOUT_MS: 30000,
        BADGE_CLASS: 'deceptive-ui-badge',
        HIGHLIGHT_CLASS: 'deceptive-ui-highlighted',
    };

    let currentReport = null;
    let remediatedCount = 0;

    // Severity color mapping
    const SEVERITY_COLORS = {
        critical: { border: '#ef4444', bg: 'rgba(239, 68, 68, 0.12)', text: '#b91c1c' },
        high: { border: '#f97316', bg: 'rgba(249, 115, 22, 0.12)', text: '#c2410c' },
        medium: { border: '#eab308', bg: 'rgba(234, 179, 8, 0.12)', text: '#a16207' },
        low: { border: '#3b82f6', bg: 'rgba(59, 130, 246, 0.12)', text: '#1d4ed8' },
    };

    /**
     * Injects base styles for highlights, tooltips, and floating HUD.
     */
    function injectStyles() {
        if (document.getElementById('deceptive-ui-engine-styles')) return;

        const styleEl = document.createElement('style');
        styleEl.id = 'deceptive-ui-engine-styles';
        styleEl.textContent = `
            .deceptive-ui-highlighted {
                position: relative !important;
                transition: outline 0.2s ease, box-shadow 0.2s ease !important;
            }
            .deceptive-ui-sev-critical {
                outline: 3px solid #ef4444 !important;
                box-shadow: 0 0 14px rgba(239, 68, 68, 0.45) !important;
            }
            .deceptive-ui-sev-high {
                outline: 3px solid #f97316 !important;
                box-shadow: 0 0 10px rgba(249, 115, 22, 0.4) !important;
            }
            .deceptive-ui-sev-medium {
                outline: 2px dashed #eab308 !important;
            }
            .deceptive-ui-sev-low {
                outline: 2px dotted #3b82f6 !important;
            }

            .deceptive-ui-badge {
                display: inline-flex;
                align-items: center;
                gap: 6px;
                padding: 4px 8px;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                font-size: 11px;
                font-weight: 700;
                border-radius: 4px;
                color: #fff;
                background: #111827;
                border: 1px solid rgba(255, 255, 255, 0.2);
                margin: 4px 0;
                z-index: 999999;
                cursor: pointer;
                box-shadow: 0 2px 8px rgba(0,0,0,0.25);
            }
            .deceptive-ui-badge-btn {
                background: #2563eb;
                color: #fff;
                border: none;
                border-radius: 3px;
                padding: 2px 6px;
                font-size: 10px;
                cursor: pointer;
                font-weight: 600;
            }
            .deceptive-ui-badge-btn:hover {
                background: #1d4ed8;
            }

            /* Floating HUD */
            #deceptive-ui-hud {
                position: fixed;
                bottom: 24px;
                right: 24px;
                width: 340px;
                background: #0f172a;
                color: #f8fafc;
                border-radius: 12px;
                border: 1px solid #334155;
                box-shadow: 0 12px 32px rgba(0, 0, 0, 0.45);
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                z-index: 2147483647;
                overflow: hidden;
                transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
            }
            #deceptive-ui-hud.minimized {
                transform: translateY(calc(100% - 48px));
            }
            .deceptive-hud-header {
                padding: 12px 16px;
                background: #1e293b;
                display: flex;
                align-items: center;
                justify-content: space-between;
                cursor: pointer;
                border-bottom: 1px solid #334155;
            }
            .deceptive-hud-title {
                font-size: 13px;
                font-weight: 700;
                display: flex;
                align-items: center;
                gap: 8px;
            }
            .deceptive-hud-body {
                padding: 14px 16px;
                font-size: 12px;
            }
            .deceptive-score-box {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 12px;
                padding: 8px 12px;
                background: #1e293b;
                border-radius: 8px;
            }
            .deceptive-score-value {
                font-size: 20px;
                font-weight: 800;
            }
            .deceptive-remediate-all-btn {
                width: 100%;
                padding: 10px;
                background: #10b981;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                font-weight: 700;
                font-size: 13px;
                cursor: pointer;
                margin-top: 10px;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 8px;
                transition: background 0.2s;
            }
            .deceptive-remediate-all-btn:hover {
                background: #059669;
            }
            .deceptive-finding-row {
                padding: 6px 0;
                border-bottom: 1px solid #1e293b;
                display: flex;
                align-items: flex-start;
                justify-content: space-between;
                gap: 8px;
            }
        `;
        document.head.appendChild(styleEl);
    }

    /**
     * Resolves DOM element using CSS selector with robust fallback.
     */
    function findTargetElement(selector) {
        if (!selector) return null;
        try {
            const el = document.querySelector(selector);
            if (el) return el;
        } catch (e) {
            // Invalid selector syntax fallback
        }

        // Fallback: match by ID without hash
        if (selector.startsWith('#')) {
            const el = document.getElementById(selector.slice(1));
            if (el) return el;
        }

        return null;
    }

    /**
     * Renders visual indicators and inline badges for every detected dark pattern.
     */
    function applyVisualHighlights(report) {
        injectStyles();
        if (!report || !report.findings) return;

        report.findings.forEach((finding, index) => {
            const el = findTargetElement(finding.selector);
            if (!el) return;

            // Apply severity outline
            el.classList.add(CONFIG.HIGHLIGHT_CLASS);
            el.classList.add(`deceptive-ui-sev-${finding.severity}`);

            // Insert indicator badge if not already added
            const existingBadge = el.parentNode?.querySelector(`[data-finding-id="${finding.id}"]`);
            if (existingBadge) return;

            const badge = document.createElement('div');
            badge.className = CONFIG.BADGE_CLASS;
            badge.dataset.findingId = finding.id;
            badge.title = `${finding.pattern_name}: ${finding.explanation}`;

            const sevColor = SEVERITY_COLORS[finding.severity] || SEVERITY_COLORS.high;
            badge.style.borderLeft = `4px solid ${sevColor.border}`;

            badge.innerHTML = `
                <span>⚠️ <b>${escapeHtml(finding.pattern_name)}</b></span>
                <button class="deceptive-ui-badge-btn" title="Execute instant remediation">Fix Now</button>
            `;

            // Inline remediation button handler
            const fixBtn = badge.querySelector('.deceptive-ui-badge-btn');
            fixBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                executeSingleRemediation(finding, el, badge);
            });

            // Insert badge right before or after element
            if (el.parentNode) {
                el.parentNode.insertBefore(badge, el);
            }
        });
    }

    /**
     * Executes remediation for a single finding.
     */
    function executeSingleRemediation(finding, el, badge) {
        if (!el) el = findTargetElement(finding.selector);
        if (!el) return;

        const directive = finding.remediation;
        const action = directive.action;

        if (action === 'uncheck') {
            if (el.checked) {
                el.checked = false;
                el.dispatchEvent(new Event('change', { bubbles: true }));
                el.dispatchEvent(new Event('input', { bubbles: true }));
            }
        } else if (action === 'neutralize_text') {
            if (directive.replacement_text) {
                el.textContent = directive.replacement_text;
            }
            if (directive.css_overrides) {
                Object.assign(el.style, directive.css_overrides);
            }
        } else if (action === 'restore_contrast') {
            if (directive.css_overrides) {
                Object.assign(el.style, directive.css_overrides);
            }
        } else if (action === 'expose_hidden_fee') {
            if (directive.css_overrides) {
                Object.assign(el.style, directive.css_overrides);
            }
            // Elevate to prominent banner
            el.style.display = 'block';
            el.style.visibility = 'visible';
        } else if (action === 'freeze_countdown') {
            // Nullify timers in element
            el.dataset.frozen = 'true';
            el.textContent = '[⏳ Countdown neutralized by Deceptive UI Shield]';
            el.style.color = '#64748b';
            el.style.fontWeight = 'bold';
        }

        // Apply general CSS overrides if provided
        if (directive.css_overrides && action !== 'neutralize_text' && action !== 'restore_contrast' && action !== 'expose_hidden_fee') {
            Object.assign(el.style, directive.css_overrides);
        }

        // Update badge to remediated state
        if (badge) {
            badge.style.background = '#065f46';
            badge.innerHTML = `<span>✅ <b>Remediated:</b> ${escapeHtml(finding.pattern_name)}</span>`;
        }

        remediatedCount++;
        updateHudStats();
    }

    /**
     * Executes all remediation directives simultaneously.
     */
    function executeAllRemediations() {
        if (!currentReport || !currentReport.findings) return;

        currentReport.findings.forEach(finding => {
            const el = findTargetElement(finding.selector);
            const badge = document.querySelector(`[data-finding-id="${finding.id}"]`);
            executeSingleRemediation(finding, el, badge);
        });

        const remediateAllBtn = document.getElementById('deceptive-hud-remediate-all');
        if (remediateAllBtn) {
            remediateAllBtn.disabled = true;
            remediateAllBtn.innerHTML = '✅ All UI Traps Neutralized';
            remediateAllBtn.style.background = '#059669';
        }
    }

    /**
     * Injects the interactive Floating HUD / Control Center.
     */
    function renderHUD(report) {
        let hud = document.getElementById('deceptive-ui-hud');
        if (!hud) {
            hud = document.createElement('div');
            hud.id = 'deceptive-ui-hud';
            document.body.appendChild(hud);
        }

        const scoreColor = report.risk_score > 50 ? '#ef4444' : report.risk_score > 20 ? '#f97316' : '#10b981';

        hud.innerHTML = `
            <div class="deceptive-hud-header" id="deceptive-hud-toggle">
                <div class="deceptive-hud-title">
                    <span>🛡️ Deceptive UI Shield</span>
                    <span style="font-size: 11px; padding: 2px 6px; border-radius: 4px; background: ${scoreColor}; font-weight: bold;">
                        ${report.risk_level}
                    </span>
                </div>
                <span id="deceptive-hud-arrow">▼</span>
            </div>
            <div class="deceptive-hud-body">
                <div class="deceptive-score-box">
                    <div>
                        <div style="color: #94a3b8; font-size: 11px;">DECEPTION RISK SCORE</div>
                        <div class="deceptive-score-value" style="color: ${scoreColor};">${report.risk_score}/100</div>
                    </div>
                    <div style="text-align: right;">
                        <div style="color: #94a3b8; font-size: 11px;">FINDINGS</div>
                        <div style="font-size: 18px; font-weight: 700;">${report.total_findings} detected</div>
                    </div>
                </div>

                <div style="max-height: 180px; overflow-y: auto; margin-bottom: 12px;" id="deceptive-findings-list">
                    ${report.findings.map(f => `
                        <div class="deceptive-finding-row">
                            <div>
                                <span style="font-weight: 600; color: #f1f5f9;">${escapeHtml(f.pattern_name)}</span>
                                <div style="font-size: 11px; color: #94a3b8;">${escapeHtml(f.deceptive_text.slice(0, 50))}...</div>
                            </div>
                            <span style="font-size: 10px; text-transform: uppercase; padding: 2px 4px; border-radius: 3px; font-weight: 700; background: ${SEVERITY_COLORS[f.severity]?.bg || '#334155'}; color: ${SEVERITY_COLORS[f.severity]?.text || '#fff'};">
                                ${f.severity}
                            </span>
                        </div>
                    `).join('')}
                </div>

                <button class="deceptive-remediate-all-btn" id="deceptive-hud-remediate-all">
                    <span>⚡ Auto-Remediate All UI Traps</span>
                </button>
            </div>
        `;

        // Toggle minimize/maximize
        const header = hud.querySelector('#deceptive-hud-toggle');
        header.addEventListener('click', () => {
            hud.classList.toggle('minimized');
            const arrow = hud.querySelector('#deceptive-hud-arrow');
            arrow.textContent = hud.classList.contains('minimized') ? '▲' : '▼';
        });

        // Remediate all button
        const remBtn = hud.querySelector('#deceptive-hud-remediate-all');
        remBtn.addEventListener('click', executeAllRemediations);
    }

    function updateHudStats() {
        const hud = document.getElementById('deceptive-ui-hud');
        if (!hud) return;
        // HUD dynamic status updates
    }

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    /**
     * Request scan from FastAPI backend for the current page URL.
     */
    async function scanCurrentPage() {
        try {
            console.log('[Deceptive UI Shield] Scanning page:', window.location.href);
            const response = await fetch(`${CONFIG.API_BASE_URL}/scan/url`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    url: window.location.href,
                    timeout_ms: CONFIG.SCAN_TIMEOUT_MS,
                    wait_for_network_idle: false,
                }),
            });

            if (!response.ok) {
                throw new Error(`API error: ${response.status} ${response.statusText}`);
            }

            const report = await response.json();
            console.log('[Deceptive UI Shield] Audit report received:', report);
            currentReport = report;

            applyVisualHighlights(report);
            renderHUD(report);
        } catch (err) {
            console.warn('[Deceptive UI Shield] Remote backend scan failed, running client-side fallback heuristics:', err);
            runClientSideHeuristicScan();
        }
    }

    /**
     * Client-side heuristic scanner fallback if the FastAPI backend is not immediately reachable.
     */
    function runClientSideHeuristicScan() {
        const findings = [];
        let idx = 0;

        // 1. Pre-checked checkboxes
        document.querySelectorAll('input[type="checkbox"]:checked').forEach(cb => {
            const label = cb.closest('label')?.innerText || cb.parentElement?.innerText || '';
            const isSuspicious = /newsletter|marketing|insurance|protect|donation|partner|tip|subscribe/i.test(label);
            if (isSuspicious) {
                findings.push({
                    id: `local-precheck-${++idx}`,
                    category: 'prechecked_box',
                    pattern_name: 'Pre-Checked Default Opt-In',
                    severity: 'high',
                    confidence: 0.90,
                    selector: cb.id ? `#${cb.id}` : 'input[type="checkbox"]:checked',
                    deceptive_text: label.trim() || 'Checked by default',
                    explanation: 'Box checked by default without affirmative user selection.',
                    remediation: { action: 'uncheck', target_selector: cb.id ? `#${cb.id}` : 'input[type="checkbox"]' },
                });
            }
        });

        // 2. Manipulative buttons (Confirm-shaming)
        document.querySelectorAll('button, a').forEach(btn => {
            const text = (btn.innerText || '').trim();
            if (/hate|prefer paying|full price|don't want|like being poor/i.test(text)) {
                findings.push({
                    id: `local-shame-${++idx}`,
                    category: 'confirm_shaming',
                    pattern_name: 'Confirm-Shaming (Manipulink)',
                    severity: 'high',
                    confidence: 0.95,
                    selector: btn.id ? `#${btn.id}` : btn.className ? `.${btn.className.split(' ')[0]}` : btn.tagName.toLowerCase(),
                    deceptive_text: text,
                    explanation: 'Decline copy shames user for opting out.',
                    remediation: { action: 'neutralize_text', replacement_text: 'No, thanks' },
                });
            }
        });

        // 3. Countdown timers
        document.querySelectorAll('.timer, .countdown, #countdown, #timer, [data-timer]').forEach(tm => {
            findings.push({
                id: `local-timer-${++idx}`,
                category: 'false_urgency',
                pattern_name: 'Fake Countdown Timer',
                severity: 'high',
                confidence: 0.88,
                selector: tm.id ? `#${tm.id}` : `.${tm.className.split(' ')[0]}`,
                deceptive_text: tm.innerText.trim() || 'Countdown timer',
                explanation: 'Dynamic timer generating artificial urgency.',
                remediation: { action: 'freeze_countdown' },
            });
        });

        // 4. Hidden fee disclaimers
        document.querySelectorAll('small, p, span, .fee-disclaimer').forEach(el => {
            const txt = (el.innerText || '').toLowerCase();
            if ((txt.includes('processing fee') || txt.includes('handling fee') || txt.includes('surcharge')) && (txt.includes('$') || txt.includes('fee'))) {
                findings.push({
                    id: `local-fee-${++idx}`,
                    category: 'hidden_fees',
                    pattern_name: 'Concealed Surcharge / Drip Pricing',
                    severity: 'critical',
                    confidence: 0.92,
                    selector: el.id ? `#${el.id}` : el.className ? `.${el.className.split(' ')[0]}` : el.tagName.toLowerCase(),
                    deceptive_text: el.innerText.trim(),
                    explanation: 'Fee disclosed in fine print rather than primary price calculation.',
                    remediation: { action: 'expose_hidden_fee', css_overrides: { display: 'block', fontSize: '14px', color: '#dc2626', fontWeight: 'bold' } },
                });
            }
        });

        const report = {
            target: window.location.href,
            scan_type: 'local_heuristic',
            risk_score: Math.min(100, findings.length * 20),
            risk_level: findings.length > 2 ? 'HIGH' : findings.length > 0 ? 'MODERATE' : 'SAFE',
            total_findings: findings.length,
            findings: findings,
        };

        currentReport = report;
        applyVisualHighlights(report);
        renderHUD(report);
    }

    // Expose Global API for console / extensions
    window.DeceptiveUIShield = {
        scan: scanCurrentPage,
        applyReport: (rep) => { currentReport = rep; applyVisualHighlights(rep); renderHUD(rep); },
        remediateAll: executeAllRemediations,
        remediateSingle: executeSingleRemediation,
    };

    // Auto-launch if configured
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', scanCurrentPage);
    } else {
        scanCurrentPage();
    }
})();
