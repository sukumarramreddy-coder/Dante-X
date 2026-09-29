export async function learningProxy(path: "/v1/calibration/learning" | "/v1/signals/manual") {
  const engine = process.env.DANTEX_ENGINE_URL ?? process.env.NEXT_PUBLIC_DANTEX_ENGINE_URL ?? "http://localhost:8000";
  try {
    const response = await fetch(engine + path, { cache: "no-store", signal: AbortSignal.timeout(25000) });
    if (!response.ok) return Response.json({ status: "UNAVAILABLE", calibration_ready: false }, { status: 503 });
    return Response.json(await response.json(), { headers: { "Cache-Control": "no-store" } });
  } catch {
    return Response.json({ status: "UNAVAILABLE", calibration_ready: false }, { status: 503 });
  }
}
