/**
 * Real-Time Deceptive UI/UX Detection and Remediation Engine
 * Extension Popup Controller (frontend/extension/popup.js)
 */

document.getElementById('scanBtn').addEventListener('click', async () => {
    const statusMsg = document.getElementById('statusMsg');
    statusMsg.textContent = 'Scanning page with AI Auditor...';

    try {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (!tab || !tab.id) {
            statusMsg.textContent = 'No active tab found';
            return;
        }

        chrome.tabs.sendMessage(tab.id, { action: 'SCAN_PAGE' }, (response) => {
            if (chrome.runtime.lastError) {
                statusMsg.textContent = 'Please refresh the active tab first';
                console.warn('[Popup] Message error:', chrome.runtime.lastError.message);
                return;
            }

            if (!response || !response.success) {
                statusMsg.textContent = response?.error ? `Scan error: ${response.error}` : 'Scan failed';
                return;
            }

            const count = response.count || 0;
            const risk = response.risk_level || 'SAFE';
            statusMsg.textContent = `Neutralized ${count} pattern(s) [Risk: ${risk}]`;
        });
    } catch (e) {
        statusMsg.textContent = `Error: ${e.message}`;
    }
});

document.getElementById('remediateBtn').addEventListener('click', async () => {
    const statusMsg = document.getElementById('statusMsg');
    try {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (!tab || !tab.id) return;

        chrome.tabs.sendMessage(tab.id, { action: 'REMEDIATE_ALL' }, (response) => {
            if (chrome.runtime.lastError) {
                statusMsg.textContent = 'Please refresh page first';
                return;
            }
            statusMsg.textContent = 'All deceptive patterns neutralized!';
        });
    } catch (e) {
        statusMsg.textContent = `Error: ${e.message}`;
    }
});
