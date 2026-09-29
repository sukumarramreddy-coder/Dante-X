export type Family = { state?: string; ce?: number; pe?: number; reasons?: string[] };
export type Structure = { last?: number; trend?: string; last_candle_ts?: string; ema9?: number; ema20?: number; atr14?: number; vwap?: number | null; opening_range_state?: string };
export type Decision = { status?: string; authorization?: string; reason?: string; direction?: string; probability?: number | null; signal_id?: string; previous_status?: string; tracking_status?: string; updated_at?: string; current_premium?: number; trigger_observed_premium?: number; expires_at?: string; contract?: { strike?: number; expiry?: string }; reference_entry?: number; reference_stop?: number; reference_t1?: number; reference_t2?: number; trade_quality?: number; contract_quality?: number };
export type Leg = { ltp?: number; oi?: number; oi_change?: number; iv?: number; spread_pct?: number; delta?: number };
export type Options = { status?: string; spot?: number; expiry?: string; atm_strike?: number; strikes?: { strike: number; call: Leg; put: Leg }[]; positioning?: { pcr_oi?: number; call_wall?: number; put_wall?: number; state?: string; scope?: string }; path_response?: { state?: string; last_sample_at?: string; samples?: number } };
export type Sample = { id: number; recorded_at: string; state?: string; decision?: Decision; market_snapshot?: { nifty_spot?: number; banknifty_spot?: number }; readiness?: { live_evidence_ready?: boolean } };
export type Dashboard = {
  fetched_at: string;
  errors: Record<string, string>;
  health: { status?: string; live_data?: { eligible?: boolean } } | null;
  observer: { state?: string; recording_hours?: string; last_persisted_at?: string; samples?: number } | null;
  duel: { state?: string; decision?: Decision; lifecycle?: Decision; pulse?: { structure?: string; option_response?: string; breadth?: string; volatility?: string }; evidence_families?: { state?: string; families?: Record<string, Family>; readiness?: { live_evidence_ready?: boolean; blocked_sources?: string[] } }; nifty?: { structure?: Structure }; banknifty?: { structure?: Structure } } | null;
  nifty: Options | null;
  banknifty: Options | null;
  signals: { events?: Decision[]; calibration_status?: string } | null;
  journal: { samples?: Sample[] } | null;
};
