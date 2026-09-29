import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import ts from 'typescript';

const source = readFileSync(new URL('../lib/api.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } });
const { getRadar } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);

test('health data cannot unlock probability or live mode', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => ({ ok: true, json: async () => ({ mode: 'live', probability_calibrated: true }) }));
  assert.deepEqual(await getRadar(), { mode: 'shadow', probability_calibrated: false, candidates: [] });
});

test('unavailable engine fails closed', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => ({ ok: false }));
  assert.equal(await getRadar(), null);
});

test('network and malformed response fail closed', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => { throw new Error('offline'); });
  assert.equal(await getRadar(), null);
  globalThis.fetch = async () => ({ ok: true, json: async () => { throw new Error('bad payload'); } });
  assert.equal(await getRadar(), null);
});
