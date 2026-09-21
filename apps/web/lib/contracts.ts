export type RadarCandidate = {
  rank: number;
  symbol: string;
  asset_class: string;
  side: string;
  score: number;
  status: "eligible" | "blocked";
  reason: string | null;
};

export type RadarResponse = {
  mode: "shadow" | "live";
  probability_calibrated: boolean;
  candidates: RadarCandidate[];
};
