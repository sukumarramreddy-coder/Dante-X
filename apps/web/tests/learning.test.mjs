import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import ts from 'typescript';

const source = readFileSync(new URL('../lib/learning-proxy.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } });
const { learningProxy } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);

test('learning proxy returns actual engine report without caching', async (t) => {
  const report = { version: 'learning-30-v1', completed_sessions: 7, calibration_ready: false };
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.ok(url.endsWith('/v1/calibration/learning'));
    assert.equal(options.cache, 'no-store');
    return { ok: true, json: async () => report };
  });
  const response = await learningProxy('/v1/calibration/learning');
  assert.deepEqual(await response.json(), report);
  assert.equal(response.headers.get('Cache-Control'), 'no-store');
});

test('learning proxy fails closed on errors and malformed JSON', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => { throw new Error('offline'); });
  let response = await learningProxy('/v1/signals/manual');
  assert.equal(response.status, 503);
  assert.equal((await response.json()).calibration_ready, false);
  globalThis.fetch = async () => ({ ok: true, json: async () => { throw new Error('bad json'); } });
  response = await learningProxy('/v1/calibration/learning');
  assert.equal(response.status, 503);
});
