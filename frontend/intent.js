/**
 * Finalytics chat intent detection.
 *
 * Pure, DOM-free logic so it can be unit-tested under Node (see
 * tests/intent.test.js) and reused by the browser UI. The browser passes the
 * current conversation context ({lastCui, lastCompany}) explicitly.
 */
(function (root) {
    // Domain acronyms that must NOT be mistaken for company names (BUG-001).
    const STOP_ACRONYMS = new Set([
        'TVA', 'CUI', 'SRL', 'SA', 'PFA', 'SRL-D', 'ANAF', 'BPI', 'ONRC',
        'CAEN', 'RO', 'EUID', 'IBAN', 'PDF', 'JSON', 'AI', 'MO', 'SC'
    ]);

    function looksLikeQuestion(text) {
        const t = (text || '').trim();
        if (/\?\s*$/.test(t)) return true;
        return /^(este|care|ce|cum|cand|când|cat|cât|de\s+ce|unde|cine|are|exista|există|imi|îmi|poti|poți|spune|zi)\b/i.test(t);
    }

    function parseMessage(text, ctx) {
        ctx = ctx || {};
        const lastCui = ctx.lastCui || null;
        const lastCompany = ctx.lastCompany || null;
        const lower = (text || '').toLowerCase();

        if (/cati.*tokens|tokens.*ai|balanta|balance|token.*left/.test(lower)) {
            return { intent: 'balance' };
        }
        if (/ce.*servicii|ce poti face|capabilities|ce stii|help|ajutor/.test(lower)) {
            return { intent: 'help' };
        }

        const cuiMatch = text.match(/\b[RC]?(\d{6,10})\b/i);
        const cui = cuiMatch ? cuiMatch[1] : null;

        // Follow-up question about an already-analyzed company (BUG-001 fix).
        if (!cui && looksLikeQuestion(text) && (lastCui || lastCompany)) {
            return { intent: 'question' };
        }

        let companyName = null;
        const capsMatch = text.match(/\b([A-ZĂÂÎȘȚ][A-ZĂÂÎȘȚ\s.\-&]{2,}(?:\sSRL|\sSA|\sSRL-D|\sPFA)?)\b/);
        if (capsMatch) {
            const candidate = capsMatch[1].trim();
            const tokens = candidate.split(/\s+/).filter(Boolean);
            const meaningful = tokens.filter(
                t => !STOP_ACRONYMS.has(t.replace(/[.\-&]/g, '').toUpperCase())
            );
            if (meaningful.length > 0) companyName = candidate;
        }

        if (!companyName) {
            const m = text.match(/(?:analizeaza|verifica|informatii|despre)\s+([^,]+?)(?:\s+cu\s+CUI|\s+CUI|$)/i);
            if (m) companyName = m[1].trim();
        }

        if (cui || companyName) {
            return { intent: 'analyze', cui, companyName };
        }
        return { intent: 'unknown' };
    }

    const api = { parseMessage, looksLikeQuestion, STOP_ACRONYMS };
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = api;
    } else {
        root.FinalyticsIntent = api;
    }
})(typeof window !== 'undefined' ? window : globalThis);
