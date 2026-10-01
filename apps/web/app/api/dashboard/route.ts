import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';
const endpoints = {
  health: '/health', observer: '/v1/observation/status', duel: '/v1/duel',
  nifty: '/v1/options/NIFTY', banknifty: '/v1/options/BANKNIFTY',
  journal: '/v1/validation/recent?limit=50', signals: '/v1/signals', review: '/v1/decision/current',
};

export async function GET() {
  const base = (process.env.DANTEX_ENGINE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
  const errors: Record<string, string> = {};
  const results = await Promise.all(Object.entries(endpoints).map(async ([key, path]) => {
    try {
      const response = await fetch(base + path, { cache: 'no-store', signal: AbortSignal.timeout(15000) });
      if (!response.ok) throw new Error('upstream');
      const value = await response.json();
      if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('shape');
      return [key, value];
    } catch {
      errors[key] = 'Source unavailable. Retry when the engine is reachable.';
      return [key, null];
    }
  }));
  return NextResponse.json({ ...Object.fromEntries(results), errors, fetched_at: new Date().toISOString() }, { headers: { 'Cache-Control': 'no-store' } });
}
