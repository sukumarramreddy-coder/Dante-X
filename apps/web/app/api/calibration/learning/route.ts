import { learningProxy } from "../../../../lib/learning-proxy";
export const dynamic = "force-dynamic";
export function GET() { return learningProxy("/v1/calibration/learning"); }
