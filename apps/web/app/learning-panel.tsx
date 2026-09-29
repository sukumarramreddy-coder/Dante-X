"use client";

import { useEffect, useState } from "react";

type Learning = {
  version: string; state: string; completed_sessions: number; target_sessions: number;
  training_samples: number; validation_samples: number; pending_samples: number;
  censored_samples: number; calibration_ready: boolean; durable: boolean;
  learned_bands: Record<string, { samples: number; wins: number; probability: number }>;
  blockers: string[]; metrics: null | { brier: number; baseline_brier: number;
    calibration_error: number; stressed_daily_lower_bound_r: number };
  collection: null | { at: string; status: string; reason: string; fresh_evidence: boolean };
};

export default function LearningPanel() {
  const [report, setReport] = useState<Learning | null>(null);
  const [error, setError] = useState("Connecting to the learning recorder…");
  const [signal, setSignal] = useState<string>("");
  useEffect(() => {
    let active = true;
    async function refresh() {
      try {
        const response = await fetch("/api/calibration/learning", { cache: "no-store", signal: AbortSignal.timeout(10000) });
        if (!response.ok) throw new Error("Learning recorder unavailable");
        const value = await response.json();
        if (value.version !== "learning-30-v1" || !Array.isArray(value.blockers) ||
            !value.learned_bands || typeof value.completed_sessions !== "number") throw new Error("Invalid learning report");
        if (active) { setReport(value); setSignal(""); setError(""); }
      } catch {
        if (active) { setReport(null); setSignal(""); setError("Learning recorder unavailable. Readiness cannot be confirmed."); }
      }
    }
    void refresh();
    const timer = setInterval(refresh, 30000);
    return () => { active = false; clearInterval(timer); };
  }, []);

  async function checkSignal() {
    setSignal("Checking current evidence…");
    try {
      const response = await fetch("/api/signals/manual", { cache: "no-store", signal: AbortSignal.timeout(30000) });
      if (!response.ok) throw new Error("Unavailable");
      const value = await response.json();
      if (value.status !== "VALIDATED_SIGNAL" || value.calibration_ready !== true || value.auto_execution !== false) {
        setSignal("WAIT — current evidence or validation gates do not support a signal."); return;
      }
      const d = value.decision;
      setSignal(`${d.direction} · ${d.contract.strike} · ${d.contract.expiry} · ${value.calibrated_probability}% validated T1-before-stop estimate. Reference entry ${d.reference_entry}, stop ${d.reference_stop}, T1 ${d.reference_t1}. As of ${value.as_of}; expires ${value.expires_at}. Manual review only; no order placed.`);
    } catch { setSignal("Signal unavailable. No order placed."); }
  }

  return <section className="evidence learning" aria-label="Calibration learning" aria-live="polite">
    <h2>30-session calibration learning</h2>
    <p>20 qualifying sessions to learn, then 10 untouched sessions to validate. Automatic orders are disabled.</p>
    {error && <p role="status">{error}</p>}
    {report && <>
      <div className="metrics">
        <div className="metric"><small>Qualifying sessions</small><strong>{report.completed_sessions} / {report.target_sessions}</strong></div>
        <div className="metric"><small>State</small><strong>{report.state.replaceAll("_", " ")}</strong></div>
        <div className="metric"><small>Training / validation outcomes</small><strong>{report.training_samples} / {report.validation_samples}</strong></div>
        <div className="metric"><small>Pending / censored outcomes</small><strong>{report.pending_samples} / {report.censored_samples}</strong></div>
      </div>
      <p>Calibration ready: <b>{report.calibration_ready ? "Yes — manual signals only" : "No"}</b>. Durable learning storage: {report.durable ? "verified" : "not verified"}.</p>
      {report.collection && <p>Last collection: {report.collection.at} · {report.collection.status} · {report.collection.reason}</p>}
      <h3>What it has learned</h3>
      {Object.keys(report.learned_bands).length === 0 ? <p>No completed qualifying training session yet. No learned win rate is claimed.</p> :
        <table><thead><tr><th>Side / score band</th><th>Outcomes</th><th>Observed target hits</th><th>Learned estimate</th></tr></thead>
          <tbody>{Object.entries(report.learned_bands).map(([key, value]) => <tr key={key}>
            <td>{key.split(":")[0]} · {Number(key.split(":")[1]) * 10}–{Number(key.split(":")[1]) * 10 + 10}%</td>
            <td>{value.samples}</td><td>{value.wins}</td><td>{(value.probability * 100).toFixed(1)}%</td>
          </tr>)}</tbody></table>}
      <p>Learned estimates remain experimental until the untouched validation window passes. A session needs at least five non-overlapping resolved setups. Missing and ambiguous outcomes are censored.</p>
      {report.metrics && <p>Validation Brier: {report.metrics.brier.toFixed(4)} (original estimate: {report.metrics.baseline_brier.toFixed(4)}). Calibration error: {(report.metrics.calibration_error * 100).toFixed(1)}%. Cost-stressed daily lower bound: {report.metrics.stressed_daily_lower_bound_r.toFixed(3)}R. These are hypothetical reference outcomes, not executed returns.</p>}
      {report.blockers.length > 0 && <><h3>What still blocks live signals</h3><ul>{report.blockers.map((reason) => <li key={reason}>{reason}</li>)}</ul></>}
      <button type="button" disabled={!report.calibration_ready} onClick={checkSignal}>Check validated manual signal</button>
      {signal && <p>{signal}</p>}
    </>}
  </section>;
}
