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

    // Detect a "compare 2+ companies" request (US7). Returns a compare intent
    // with a list of {cui, companyName} refs, or null if it is not a compare.
    function parseCompare(text) {
        const t = (text || '').trim();
        if (!/\b(compar\w*|versus|vs)\b/i.test(t)) return null;

        // Prefer CUIs: they are unambiguous.
        const cuis = [];
        const re = /\b[RC]?(\d{6,10})\b/gi;
        let m;
        while ((m = re.exec(t)) !== null) cuis.push(m[1]);
        if (cuis.length >= 2) {
            return { intent: 'compare', companies: cuis.map(c => ({ cui: c, companyName: null })) };
        }

        // Otherwise split the text after the trigger word into company names.
        const rest = t.replace(/^.*?\b(compar\w*|versus|vs)\b/i, '');
        const names = rest
            .split(/\s+(?:cu|vs|versus|si|și|şi|sau|\/)\s+|,/i)
            .map(s => s.replace(/\b[RC]?\d{6,10}\b/g, '').replace(/\bCUI\b/ig, '').trim())
            .filter(s => s.length >= 2 && /[A-Za-zĂÂÎȘȚăâîșț]/.test(s) &&
                !STOP_ACRONYMS.has(s.replace(/[.\-&]/g, '').toUpperCase()));
        if (names.length >= 2) {
            return { intent: 'compare', companies: names.map(n => ({ cui: null, companyName: n })) };
        }
        if (cuis.length === 1 && names.length === 1) {
            return {
                intent: 'compare',
                companies: [{ cui: cuis[0], companyName: null }, { cui: null, companyName: names[0] }],
            };
        }
        return null;
    }

    // Normalize and cap user-attached documents before sending them to the LLM
    // context. Drops empty docs, caps the count and per-document length so the
    // request stays bounded (mirrors the server-side cap).
    function sanitizeDocuments(docs, opts) {
        opts = opts || {};
        const maxDocs = opts.maxDocs || 8;
        const maxChars = opts.maxChars || 8000;
        const out = [];
        for (const d of (docs || [])) {
            if (out.length >= maxDocs) break;
            const content = (d && d.content != null ? String(d.content) : '').trim();
            if (!content) continue;
            const name = (d && d.name ? String(d.name) : 'document').slice(0, 120);
            out.push({ name: name, content: content.slice(0, maxChars) });
        }
        return out;
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

        // Compare 2+ companies (US7) — must be checked before single-company analyze.
        const cmp = parseCompare(text);
        if (cmp) return cmp;

        const cuiMatch = text.match(/\b[RC]?(\d{6,10})\b/i);
        const cui = cuiMatch ? cuiMatch[1] : null;

        // Follow-up question about an already-analyzed company (BUG-001 fix).
        if (!cui && looksLikeQuestion(text) && (lastCui || lastCompany)) {
            return { intent: 'question' };
        }

        let companyName = null;
        const capsMatch = text.match(/\b([A-Z0-9ĂÂÎȘȚ][A-Z0-9ĂÂÎȘȚ\s.\-&]{2,}(?:\sSRL|\sSA|\sSRL-D|\sPFA)?)\b/);
        if (capsMatch) {
            const candidate = capsMatch[1].trim();
            const tokens = candidate.split(/\s+/).filter(Boolean);
            const meaningful = tokens.filter(
                t => !STOP_ACRONYMS.has(t.replace(/[.\-&]/g, '').toUpperCase())
            );
            // Require at least one alphabetic character so bare numbers are not
            // mistaken for a company name.
            if (meaningful.length > 0 && /[A-ZĂÂÎȘȚ]/.test(candidate)) companyName = candidate;
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

    const api = { parseMessage, looksLikeQuestion, parseCompare, sanitizeDocuments, STOP_ACRONYMS };
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = api;
    } else {
        root.FinalyticsIntent = api;
    }
})(typeof window !== 'undefined' ? window : globalThis);
