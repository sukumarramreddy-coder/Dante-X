import type { RadarResponse } from "./contracts";

const ENGINE = process.env.NEXT_PUBLIC_DANTEX_ENGINE_URL ?? "http://localhost:8000";

export async function getRadar(): Promise<RadarResponse | null> {
  try {
    const response = await fetch(ENGINE + "/health", { cache: "no-store" });
    if (!response.ok) return null;
    const health = await response.json();
    return {
      mode: health.mode ?? "shadow",
      probability_calibrated: Boolean(health.probability_calibrated),
      candidates: [],
    };
  } catch {
    return null;
  }
}
