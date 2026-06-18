/**
 * Regression tests for chat intent detection, including BUG-001
 * (acronyms like "TVA" must not be parsed as company names).
 *
 * Run: node --test  (from the frontend/ directory)
 */
const test = require('node:test');
const assert = require('node:assert');
const { parseMessage } = require('../intent.js');

test('CUI is detected and yields analyze intent', () => {
    const r = parseMessage('analizeaza CUI 14388248', {});
    assert.strictEqual(r.intent, 'analyze');
    assert.strictEqual(r.cui, '14388248');
});

test('company name in caps yields analyze intent', () => {
    const r = parseMessage('verifica INTERNET TEAM SRL', {});
    assert.strictEqual(r.intent, 'analyze');
    assert.match(r.companyName, /INTERNET TEAM/);
});

test('BUG-001: question containing TVA is NOT a new analysis', () => {
    const ctx = { lastCui: '14388248', lastCompany: 'INTERNET TEAM SRL' };
    const r = parseMessage('Este firma platitoare de TVA si de cat timp exista?', ctx);
    assert.strictEqual(r.intent, 'question');
});

test('BUG-001: bare acronym is not treated as a company name', () => {
    const r = parseMessage('TVA', {});
    assert.strictEqual(r.intent, 'unknown');
});

test('question without prior context falls through to unknown', () => {
    const r = parseMessage('Este firma activa?', {});
    assert.strictEqual(r.intent, 'unknown');
});

test('explicit CUI in a question still analyzes (CUI wins)', () => {
    const ctx = { lastCui: '111', lastCompany: 'X' };
    const r = parseMessage('Care e scorul pentru CUI 49068564?', ctx);
    assert.strictEqual(r.intent, 'analyze');
    assert.strictEqual(r.cui, '49068564');
});

test('balance and help intents still work', () => {
    assert.strictEqual(parseMessage('cati tokens am?', {}).intent, 'balance');
    assert.strictEqual(parseMessage('ce servicii ai?', {}).intent, 'help');
});

test('follow-up question with company name in caps routes to Q&A', () => {
    const ctx = { lastCui: '14388248', lastCompany: 'INTERNET TEAM SRL' };
    const r = parseMessage('Care este cel mai mare risc?', ctx);
    assert.strictEqual(r.intent, 'question');
});

test('US7: compare two CUIs yields compare intent with both companies', () => {
    const r = parseMessage('compara CUI 14388248 cu CUI 49068564', {});
    assert.strictEqual(r.intent, 'compare');
    assert.strictEqual(r.companies.length, 2);
    assert.deepStrictEqual(r.companies.map(c => c.cui), ['14388248', '49068564']);
});

test('US7: compare two company names yields compare intent', () => {
    const r = parseMessage('compara INTERNET TEAM SRL vs ALTA FIRMA SRL', {});
    assert.strictEqual(r.intent, 'compare');
    assert.strictEqual(r.companies.length, 2);
    assert.match(r.companies[0].companyName, /INTERNET TEAM/);
    assert.match(r.companies[1].companyName, /ALTA FIRMA/);
});

test('US7: three CUIs compare', () => {
    const r = parseMessage('compara 14388248, 49068564 si 24506022', {});
    assert.strictEqual(r.intent, 'compare');
    assert.strictEqual(r.companies.length, 3);
});

test('US7: compare with a single CUI is not a compare (falls back to analyze)', () => {
    const r = parseMessage('compara CUI 14388248', {});
    assert.strictEqual(r.intent, 'analyze');
    assert.strictEqual(r.cui, '14388248');
});

test('a normal analyze request is not misread as compare', () => {
    const r = parseMessage('analizeaza CUI 14388248', {});
    assert.strictEqual(r.intent, 'analyze');
});

test('alphanumeric company name (INT80 SRL) is parsed as analyze', () => {
    const r = parseMessage('analizeaza INT80 SRL', {});
    assert.strictEqual(r.intent, 'analyze');
    assert.match(r.companyName, /INT80/);
});

test('glued alphanumeric name (INT80SRL) is parsed as analyze', () => {
    const r = parseMessage('INT80SRL', {});
    assert.strictEqual(r.intent, 'analyze');
    assert.match(r.companyName, /INT80SRL/);
});

test('bare lowercase name with SRL suffix is parsed as analyze', () => {
    const r = parseMessage('int80 srl', {});
    assert.strictEqual(r.intent, 'analyze');
    assert.match(r.companyName, /int80 srl/i);
});

test('glued lowercase name ending in srl is parsed as analyze', () => {
    const r = parseMessage('int80srl', {});
    assert.strictEqual(r.intent, 'analyze');
});

test('common phrase with "sa" is NOT misread as a company', () => {
    assert.strictEqual(parseMessage('ce sa fac acum', {}).intent, 'unknown');
});

// ── Document attachments added to the LLM context ──
const { sanitizeDocuments } = require('../intent.js');

test('sanitizeDocuments drops empty docs and trims content', () => {
    const out = sanitizeDocuments([
        { name: 'a.txt', content: '  hello  ' },
        { name: 'empty.txt', content: '   ' },
        { name: 'none.txt', content: null },
    ]);
    assert.strictEqual(out.length, 1);
    assert.strictEqual(out[0].name, 'a.txt');
    assert.strictEqual(out[0].content, 'hello');
});

test('sanitizeDocuments caps document count', () => {
    const many = Array.from({ length: 20 }, (_, i) => ({ name: `d${i}.txt`, content: 'x' }));
    const out = sanitizeDocuments(many, { maxDocs: 8 });
    assert.strictEqual(out.length, 8);
});

test('sanitizeDocuments caps per-document length', () => {
    const out = sanitizeDocuments([{ name: 'big.txt', content: 'y'.repeat(50000) }], { maxChars: 8000 });
    assert.strictEqual(out[0].content.length, 8000);
});

test('sanitizeDocuments defaults a missing name', () => {
    const out = sanitizeDocuments([{ content: 'data' }]);
    assert.strictEqual(out[0].name, 'document');
});

test('sanitizeDocuments handles empty/undefined input', () => {
    assert.deepStrictEqual(sanitizeDocuments(), []);
    assert.deepStrictEqual(sanitizeDocuments([]), []);
});
