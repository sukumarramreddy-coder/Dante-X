import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import ts from 'typescript';
const source = readFileSync(new URL('../lib/probability.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } });
const { directionalDisplay } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
test('uncalibrated WAIT still renders both directional preferences', () => {
  const result = directionalDisplay({status:'PROVISIONAL', fresh_evidence:true, directional:{ce:62,pe:38}});
  assert.equal(result.ce, '62%'); assert.equal(result.pe, '38%');
  assert.match(result.label, /not profit odds or trade authorization/);
  assert.equal(result.authorization, undefined);
});
test('missing, malformed and stale evidence stays explicit', () => {
  for (const directional of [undefined, {ce:NaN,pe:50}, {ce:80,pe:80}])
    assert.equal(directionalDisplay({directional}).ce, 'Unavailable');
  const result = directionalDisplay({status:'PRIOR_ONLY',fresh_evidence:false,directional:{ce:50,pe:50},blocked_sources:['NIFTY_STRUCTURE']});
  assert.match(result.label,/Neutral prior only/);
  assert.deepEqual(result.reasons,['NIFTY_STRUCTURE']);
});
