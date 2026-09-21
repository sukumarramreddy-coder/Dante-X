from fastapi import FastAPI
from .radar import RadarInputs, opportunity_score

app = FastAPI(title="Dante X Engine", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok", "service": "dante-x-engine"}


@app.post("/v1/radar/score")
def radar_score(inputs: RadarInputs):
    return {
        "opportunity_score": opportunity_score(inputs),
        "is_probability": False,
        "label": "uncalibrated opportunity score",
    }
