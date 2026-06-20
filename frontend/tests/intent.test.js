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
