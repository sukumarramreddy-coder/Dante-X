import type { ProbabilityReview } from './dashboard';

export function directionalDisplay(review?: ProbabilityReview) {
  const ce = review?.directional?.ce, pe = review?.directional?.pe;
  const valid = typeof ce === 'number' && typeof pe === 'number' &&
    Number.isFinite(ce) && Number.isFinite(pe) && ce >= 0 && ce <= 100 &&
    pe >= 0 && pe <= 100 && Math.abs(ce + pe - 100) < .01;
  const fresh = review?.fresh_evidence === true;
  return {
    ce: valid ? `${ce}%` : 'Unavailable',
    pe: valid ? `${pe}%` : 'Unavailable',
    quality: valid ? fresh ? 'Fresh evidence' : 'Stale or missing evidence' : 'Unavailable',
    label: valid ? fresh && review?.status === 'PROVISIONAL'
      ? 'Provisional heuristic directional preference. Uncalibrated; not profit odds or trade authorization.'
      : 'Neutral prior only. Uncalibrated; not a current directional signal or profit odds.'
      : 'Directional probability unavailable: engine evidence missing.',
    reasons: [...(review?.blocked_sources || []), ...(review?.data_reasons || []), ...(review?.missing_families || [])],
  };
}
