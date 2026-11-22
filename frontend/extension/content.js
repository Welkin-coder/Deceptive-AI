/**
 * Extension Content Script Bridge
 * Communicates with popup.js and background workers, triggers scans, and applies remediations.
 */

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "SCAN_PAGE") {
        if (window.DeceptiveUIShield) {
            window.DeceptiveUIShield.scan()
                .then(() => sendResponse({ status: "success" }))
                .catch(err => sendResponse({ status: "error", message: err.message }));
            return true; // async response
        } else {
            sendResponse({ status: "not_loaded" });
        }
    } else if (request.action === "REMEDIATE_ALL") {
        if (window.DeceptiveUIShield) {
            window.DeceptiveUIShield.remediateAll();
            sendResponse({ status: "success" });
        }
    }
});
