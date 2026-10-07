from __future__ import annotations

from contextlib import asynccontextmanager
from math import isfinite
from dataclasses import asdict
from urllib.error import HTTPError, URLError

from fastapi import FastAPI

from .providers.credentials import UpstoxCredentials
from .providers.upstox import UpstoxConfig
from .providers.upstox_rest import UpstoxRestClient
from .providers.upstox_live import nifty_live_probe
from .providers.upstox_core_live import core_live_feed
from .providers.upstox_master import instrument_master
from .providers.options_intelligence import options_intelligence
from .option_duel import duel
from .evidence_families import evidence_families, recompute_consensus
from .momentum import momentum_family, cross_index_momentum
from .breadth import breadth_family, sector_leadership_family, volatility_family, NIFTY_BREADTH_KEYS, SECTOR_INDEX_KEYS, INDIA_VIX_KEY
from .observation_loop import observation_loop
from .providers.structure_live import structure_snapshot
from .freshness import gate as freshness_gate, market_session, system_readiness
from .derivatives import derivatives_positioning_family
from .decision import shadow_decision
from .challengers import challenger_status
from .learning_runtime import learning_window, collect_learning
from .validation_recorder import validation_recorder
from .expert_runtime import DecisionRuntime
from .shadow_lifecycle import ShadowLifecycle
from .positioning import positioning_snapshot
from .market_pulse import build_market_pulse
from .replay_capture import quote_capture, replay_capture
from .paper_desk import PaperDesk, mt5_shell
from pathlib import Path
import os

decision_runtime = DecisionRuntime(validation_recorder)
paper_desk = PaperDesk(Path(os.getenv(
    "DANTEX_PAPER_DB",
    str(Path(validation_recorder.path).with_name("dantex-paper.sqlite3")),
)))


def review_expert_safely(options, structures, families):
    try:
        decision_runtime.evaluate(options, structures, families)
    except Exception:
        # An optional review must never interrupt the established deterministic pipeline.
        decision_runtime.last_error = "EXPERT_REVIEW_UNAVAILABLE"

@asynccontextmanager
async def lifespan(app: FastAPI):
    start_shadow_observers()
    yield


app = FastAPI(title="Dante X Engine", version="0.1.0", lifespan=lifespan)

def _previous_close(item):
    """Use valid prior-close data; intraday OHLC close is not prior close."""
    def finite_number(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)

    ltp = item.get("last_price") or item.get("ltp")
    net = item.get("net_change")
    if finite_number(ltp) and ltp > 0 and finite_number(net):
        previous = ltp - net
        if finite_number(previous) and previous > 0:
            return previous
    for key in ("prev_close", "prev_close_price"):
        previous = item.get(key)
        if finite_number(previous) and previous > 0:
            return previous
    return None


def start_shadow_observers():
    """Start read-only background observers with the service process."""
    core_live_feed.start()
    instrument_master.refresh_async()
    observation_loop.start()


@app.get("/health")
def health():
    observer = observation_loop.snapshot()
    validation = validation_recorder.status()
    live = bool(observer.get("live_observation_eligible"))
    paper = paper_desk.status()
    return {
        "status": "ok" if live else "degraded",
        "service": "dante-x-engine",
        "live_data": {
            "status": observer.get("freshness"),
            "age_seconds": observer.get("age_seconds"),
            "eligible": live,
            "last_sample_at": observer.get("last_sample_at"),
            "last_persisted_at": observer.get("last_persisted_at"),
        },
        "durable_sink": validation.get("external_write"),
        "paper": paper,
        "mt5": mt5_shell(),
        "live_orders": False,
    }


@app.get("/v1/paper/status")
def paper_status():
    return paper_desk.status()


@app.post("/v1/paper/kill")
def paper_kill():
    return paper_desk.kill()


@app.post("/v1/paper/release")
def paper_release():
    return paper_desk.release()


@app.get("/v1/mt5/status")
def mt5_status():
    return mt5_shell()


@app.get("/v1/structure/{symbol}")
def live_structure(symbol: str):
    """Read-only intraday structure: VWAP, OR, EMA, ATR and prior-day levels."""
    normalized = symbol.upper()
    if normalized not in {"NIFTY", "BANKNIFTY"}:
        return {"status": "UNSUPPORTED_SYMBOL", "symbol": normalized, "mode": "shadow"}
    try:
        return structure_snapshot(normalized)
    except Exception as exc:
        return {"symbol": normalized, "status": "DEGRADED", "error": type(exc).__name__, "mode": "shadow"}


@app.get("/v1/observation/status")
def observation_status():
    """Background SHADOW sampler health."""
    observation_loop.start()
    return observation_loop.snapshot()


def paper_lifecycle(decision, families, options):
    try:
        return ShadowLifecycle(validation_recorder.path).advance(decision, families, options)
    except Exception:
        return {"status": "WAIT", "authorization": "NONE", "probability": None,
                "tracking_status": "UNAVAILABLE", "simulation": True,
                "reason": "Paper lifecycle persistence unavailable; authorization blocked."}


@app.get("/v1/signals")
def signals():
    return ShadowLifecycle(validation_recorder.path).snapshot()


@app.get("/v1/duel")
def option_duel():
    """SHADOW CE-vs-PE evidence duel across NIFTY and BANKNIFTY."""
    return build_option_duel()


def build_option_duel(snapshots=None):
    """Shared by the API and background learner; reuses an observer snapshot."""
    instrument_master.refresh_async()
    nifty = snapshots["NIFTY"] if snapshots else options_intelligence.snapshot("NIFTY")
    bank = snapshots["BANKNIFTY"] if snapshots else options_intelligence.snapshot("BANKNIFTY")
    if nifty.get("status") != "OK" or bank.get("status") != "OK":
        review_expert_safely({"NIFTY": nifty, "BANKNIFTY": bank}, {}, {})
        return {"state": "DATA_NOT_READY", "nifty_status": nifty.get("status"), "banknifty_status": bank.get("status"), "mode": "shadow",
                "decision": shadow_decision({}, {"live_evidence_ready": False}, {})}
    return evaluate_option_duel(nifty, bank)


def evaluate_option_duel(nifty=None, bank=None):
    """Accept the observer's exact samples rather than fetching a second pair."""
    instrument_master.refresh_async()
    nifty = nifty if nifty is not None else options_intelligence.snapshot("NIFTY")
    bank = bank if bank is not None else options_intelligence.snapshot("BANKNIFTY")
    if nifty.get("status") != "OK" or bank.get("status") != "OK":
        validation_recorder.record_duel(
            {"state": "DATA_NOT_READY", "readiness": {"live_evidence_ready": False}},
            {"status": "NO_SETUP", "authorization": "NONE", "reason": "option snapshots unavailable"},
            {"replay": replay_capture(options={"NIFTY": nifty, "BANKNIFTY": bank}, kind="data_not_ready")},
        )
        return {"state": "DATA_NOT_READY", "nifty_status": nifty.get("status"), "banknifty_status": bank.get("status"), "mode": "shadow"}
    nifty_structure = structure_snapshot("NIFTY")
    bank_structure = structure_snapshot("BANKNIFTY")
    families = evidence_families(nifty, bank, nifty_structure, bank_structure)
    session = market_session()
    families["freshness"] = {"session": session}
    n_path = nifty.get("path_response") or {}
    b_path = bank.get("path_response") or {}
    n_options_gate = freshness_gate(source="NIFTY_OPTIONS", timestamp=n_path.get("last_sample_at"), session_date=n_path.get("session_date"), provider_fresh=nifty.get("evidence_eligible", False))
    b_options_gate = freshness_gate(source="BANKNIFTY_OPTIONS", timestamp=b_path.get("last_sample_at"), session_date=b_path.get("session_date"), provider_fresh=bank.get("evidence_eligible", False))
    families["freshness"]["nifty_options"] = n_options_gate
    families["freshness"]["banknifty_options"] = b_options_gate
    if not (n_options_gate["eligible"] and b_options_gate["eligible"]):
        families["families"]["options_response"] = {
            "state":"STALE_CONTEXT","ce":0.0,"pe":0.0,
            "quality":{"freshness":"CENTRAL_GATE_BLOCKED"},
            "reasons":n_options_gate["reasons"] + b_options_gate["reasons"],
        }
        families["families"]["cross_index"] = {
            "state":"STALE_CONTEXT","ce":0.0,"pe":0.0,
            "quality":{"freshness":"CENTRAL_GATE_BLOCKED"},
            "reasons":["cross-index path requires fresh NIFTY and BANKNIFTY option observations"],
        }
    # Momentum is a live-session family. Historical fallback candles remain
    # visible as context but must never be reinterpreted as current velocity.
    n_structure_gate = freshness_gate(source="NIFTY_STRUCTURE", timestamp=nifty_structure.get("last_candle_ts"), session_date=nifty_structure.get("session_date"), provider_fresh=nifty_structure.get("evidence_eligible"))
    b_structure_gate = freshness_gate(source="BANKNIFTY_STRUCTURE", timestamp=bank_structure.get("last_candle_ts"), session_date=bank_structure.get("session_date"), provider_fresh=bank_structure.get("evidence_eligible"))
    families["freshness"]["nifty_structure"] = n_structure_gate
    families["freshness"]["banknifty_structure"] = b_structure_gate
    if not n_structure_gate["eligible"]:
        n_momentum = {"state":"STALE_CONTEXT","ce":0.0,"pe":0.0,
                      "quality":{"freshness":nifty_structure.get("freshness"),"session_date":nifty_structure.get("session_date")},
                      "reasons":["historical structure candles blocked from live momentum"]}
    else:
        n_momentum = momentum_family(nifty_structure.get("recent_candles") or [])
    if not b_structure_gate["eligible"]:
        b_momentum = {"state":"STALE_CONTEXT","ce":0.0,"pe":0.0,
                      "quality":{"freshness":bank_structure.get("freshness"),"session_date":bank_structure.get("session_date")},
                      "reasons":["historical structure candles blocked from live momentum"]}
    else:
        b_momentum = momentum_family(bank_structure.get("recent_candles") or [])
    families["families"]["momentum_velocity"] = cross_index_momentum(n_momentum, b_momentum)
    # Breadth is fetched independently from actual liquid constituents. Fail
    # closed on provider/shape errors; never turn missing breadth into a vote.
    quote_inputs = {}
    try:
        client = UpstoxRestClient(UpstoxConfig(access_token=UpstoxCredentials.from_env().analytics_token))
        payload = client.full_market_quotes(NIFTY_BREADTH_KEYS)
        quote_inputs["breadth"] = quote_capture(NIFTY_BREADTH_KEYS, payload)
        raw = (payload.get("data") or {})
        quotes = []
        for item in raw.values() if isinstance(raw, dict) else []:
            if not isinstance(item, dict):
                continue
            quotes.append({
                "ltp": item.get("last_price") or item.get("ltp"),
                "prev_close": _previous_close(item),
            })
        breadth_timestamps = [
            item.get("timestamp") for item in raw.values()
            if isinstance(item, dict) and item.get("timestamp")
        ] if isinstance(raw, dict) else []
        breadth_timestamp = min(breadth_timestamps) if breadth_timestamps else None
        breadth_gate = freshness_gate(source="BREADTH", timestamp=breadth_timestamp, quote_response=True)
        families["freshness"]["breadth"] = breadth_gate
        families["families"]["breadth"] = breadth_family(quotes) if breadth_gate["eligible"] else {
            "state":"STALE_CONTEXT","ce":0.0,"pe":0.0,
            "quality":{"freshness":"CENTRAL_GATE_BLOCKED"},
            "reasons":breadth_gate["reasons"],
        }
        sector_payload = client.full_market_quotes(list(SECTOR_INDEX_KEYS.values()))
        quote_inputs["sector_leadership"] = quote_capture(list(SECTOR_INDEX_KEYS.values()), sector_payload)
        sector_raw = sector_payload.get("data") or {}
        sector_quotes = {}
        for name, key in SECTOR_INDEX_KEYS.items():
            # Provider response keys may use instrument token or symbol form;
            # match exact key first, then normalized instrument-token suffix.
            item = sector_raw.get(key)
            if item is None and isinstance(sector_raw, dict):
                item = next((v for k,v in sector_raw.items()
                             if isinstance(v,dict) and (k == key or v.get("instrument_token") == key)), None)
            if isinstance(item, dict):
                sector_quotes[name] = {"ltp":item.get("last_price") or item.get("ltp"),
                                       "prev_close":_previous_close(item)}
        sector_timestamps = [
            item.get("timestamp") for item in sector_raw.values()
            if isinstance(item, dict) and item.get("timestamp")
        ] if isinstance(sector_raw, dict) else []
        sector_timestamp = min(sector_timestamps) if sector_timestamps else None
        sector_gate = freshness_gate(source="SECTOR_LEADERSHIP", timestamp=sector_timestamp, quote_response=True)
        families["freshness"]["sector_leadership"] = sector_gate
        families["families"]["sector_leadership"] = sector_leadership_family(sector_quotes) if sector_gate["eligible"] else {
            "state":"STALE_CONTEXT","ce":0.0,"pe":0.0,
            "quality":{"freshness":"CENTRAL_GATE_BLOCKED"},
            "reasons":sector_gate["reasons"],
        }
        vix_payload = client.full_market_quotes([INDIA_VIX_KEY])
        quote_inputs["volatility"] = quote_capture([INDIA_VIX_KEY], vix_payload)
        vix_raw = vix_payload.get("data") or {}
        vix_item = vix_raw.get(INDIA_VIX_KEY)
        if vix_item is None and isinstance(vix_raw, dict):
            vix_item = next((v for k,v in vix_raw.items()
                             if isinstance(v,dict) and (k == INDIA_VIX_KEY or v.get("instrument_token") == INDIA_VIX_KEY)), None)
        if isinstance(vix_item, dict):
            vix_quote = {"ltp":vix_item.get("last_price") or vix_item.get("ltp"),
                         "prev_close":_previous_close(vix_item)}
            vix_gate = freshness_gate(source="INDIA_VIX", timestamp=vix_item.get("timestamp"), quote_response=True)
            families["freshness"]["volatility"] = vix_gate
            families["families"]["volatility"] = volatility_family(vix_quote) if vix_gate["eligible"] else {
                "state":"STALE_CONTEXT","ce":0.0,"pe":0.0,
                "metrics":{"vix":vix_quote.get("ltp")},
                "quality":{"freshness":"CENTRAL_GATE_BLOCKED"},
                "reasons":vix_gate["reasons"],
            }
        else:
            families["families"]["volatility"] = volatility_family({})
    except Exception as exc:
        quote_inputs["error_type"] = type(exc).__name__
        families["families"]["breadth"] = {
            "state":"UNAVAILABLE","ce":0.0,"pe":0.0,
            "quality":{"usable":0,"required":10},
            "reasons":[f"breadth provider unavailable: {type(exc).__name__}"],
        }
        families["families"]["sector_leadership"] = {
            "state":"UNAVAILABLE","ce":0.0,"pe":0.0,
            "quality":{"usable":0,"required":5},
            "reasons":[f"sector provider unavailable: {type(exc).__name__}"],
        }
        families["families"]["volatility"] = {
            "state":"UNAVAILABLE","ce":0.0,"pe":0.0,
            "quality":{"usable":False},
            "reasons":[f"India VIX provider unavailable: {type(exc).__name__}"],
        }
    # Derivatives are one consolidated family: OI/PCR/IV never become separate votes.
    if (n_options_gate["eligible"] and b_options_gate["eligible"]
            and nifty.get("derivatives_evidence_eligible") is True
            and bank.get("derivatives_evidence_eligible") is True):
        families["families"]["derivatives_positioning"] = derivatives_positioning_family(nifty, bank)
    else:
        families["families"]["derivatives_positioning"] = {
            "state":"STALE_CONTEXT","ce":0.0,"pe":0.0,
            "quality":{"freshness":"CENTRAL_GATE_BLOCKED"},
            "reasons":["derivatives require fresh option-chain observations"],
        }
    # One vote per independent family; correlated per-index observations are
    # synthesized before consensus.
    consensus = recompute_consensus(families["families"])
    families["state"] = consensus["state"]
    families["family_counts"] = consensus["family_counts"]
    families["readiness"] = system_readiness(families["freshness"], families["families"])
    decision = shadow_decision(families, families["readiness"], nifty)
    # Additive shadow review; never changes the existing learner or manual signal.
    lifecycle = paper_lifecycle(decision, families, nifty)
    pulse = asdict(build_market_pulse(symbol="NIFTY", spot=nifty.get("spot"),
        structure={"state": nifty_structure.get("trend")}, options=nifty,
        breadth=families["families"].get("breadth", {}), volatility=families["families"].get("volatility", {}),
        freshness={"eligible": families["readiness"]["live_evidence_ready"]},
        counterweights=families["readiness"]["blocked_sources"]))
    validation_recorder.record_duel(families, decision, {
        "nifty_spot": nifty.get("spot"), "banknifty_spot": bank.get("spot"),
        "nifty_expiry": nifty.get("expiry"), "banknifty_expiry": bank.get("expiry"),
        "nifty_structure": {k:nifty_structure.get(k) for k in ("last","trend","opening_range_state","session_date","freshness")},
        "banknifty_structure": {k:bank_structure.get(k) for k in ("last","trend","opening_range_state","session_date","freshness")},
        "replay": replay_capture(
            options={"NIFTY": nifty, "BANKNIFTY": bank},
            structures={"NIFTY": nifty_structure, "BANKNIFTY": bank_structure},
            quotes=quote_inputs, families=families, lifecycle=lifecycle),
    })
    review_expert_safely(
        {"NIFTY": nifty, "BANKNIFTY": bank},
        {"NIFTY": nifty_structure, "BANKNIFTY": bank_structure},
        families,
    )
    return {
        "decision": decision,
        "lifecycle": lifecycle,
        "pulse": pulse,
        "duel": duel(nifty, bank, nifty_structure, bank_structure),
        "evidence_families": families,
        "nifty": {"path": nifty["path_response"], "structure": nifty_structure},
        "banknifty": {"path": bank["path_response"], "structure": bank_structure},
        "mode": "shadow",
    }


def run_learning_cycle(snapshots, now=None, *, evaluated_payload=None):
    window = learning_window()
    active = market_session(now)["market_open"]
    payload = (evaluated_payload if evaluated_payload is not None else
               build_option_duel(snapshots)) if active else {}
    if not active and not window.pending(now):
        return window.report(now)
    client = UpstoxRestClient(UpstoxConfig(access_token=UpstoxCredentials.from_env().analytics_token))
    # Stamp prediction after evidence collection, never at the start of the
    # potentially slow provider requests.
    return collect_learning(payload.get("decision") or {}, client, window=window)


@app.get("/v1/calibration/learning")
def calibration_learning():
    return learning_window().report()


@app.get("/v1/decision/current")
def current_decision():
    """Observer-produced result. UI polling never triggers paid expert calls."""
    return decision_runtime.current()


@app.get("/v1/decision/history")
def decision_history(limit: int = 50):
    return {"schema_version": "1.0", "mode": "shadow", "evaluations": decision_runtime.history(limit)}


@app.get("/v1/expert/status")
def expert_status():
    return decision_runtime.provider.status()


@app.get("/v1/signals/manual")
def manual_signal():
    """Live publication only after OOS gates pass; no broker order capability."""
    payload = build_option_duel()
    return learning_window().publish(payload.get("decision") or {})


@app.get("/v1/challengers/status")
def probability_challengers():
    """Read-only artifact availability; no training or model upload surface."""
    return challenger_status()


@app.get("/v1/validation/recent")
def validation_recent(limit: int = 100):
    limit=max(1,min(limit,500))
    return {"samples":validation_recorder.recent(limit),"mode":"shadow"}


@app.get("/v1/validation/status")
def validation_status():
    # Record a diagnostic heartbeat so this endpoint proves SQLite writes
    # independently of whether /v1/duel completed successfully.
    try:
        validation_recorder.record_duel(
            {"state":"DIAGNOSTIC","family_counts":{},"readiness":{"diagnostic":True}},
            {"status":"VALIDATION_HEARTBEAT","authorization":"NONE"},
        )
    except Exception as exc:
        status=validation_recorder.status()
        status["write_test"]="FAILED"
        status["write_error"]=type(exc).__name__
        return status
    status=validation_recorder.status()
    status["write_test"]="OK"
    return status


@app.get("/v1/options/{symbol}")
def options_snapshot(symbol: str):
    """Nearest-expiry ATM neighborhood with read-only Upstox chain/Greeks."""
    normalized = symbol.upper()
    if normalized not in {"NIFTY", "BANKNIFTY"}:
        return {"status": "UNSUPPORTED_SYMBOL", "symbol": normalized, "mode": "shadow"}
    instrument_master.refresh_async()
    snapshot = options_intelligence.snapshot(normalized)
    if snapshot.get("status") == "OK":
        positioning = asdict(positioning_snapshot(snapshot.get("strikes") or [], spot=snapshot.get("spot")))
        snapshot["positioning"] = positioning
        snapshot["positioning"]["scope"] = "Returned ATM neighborhood only; not the full chain"
    return snapshot


@app.get("/v1/market/state")
def market_state():
    """SHADOW core market state for NIFTY/BANKNIFTY plus instrument-master health."""
    core_live_feed.start()
    instrument_master.refresh_async()
    return {
        "feed": core_live_feed.snapshot(),
        "instrument_master": {
            "nifty": instrument_master.index_derivatives("NIFTY"),
            "banknifty": instrument_master.index_derivatives("BANKNIFTY"),
        },
        "mode": "shadow",
    }


@app.get("/v1/providers/upstox/live")
def upstox_live():
    """Start/read the SHADOW NIFTY V3 heartbeat. No order capability."""
    nifty_live_probe.start()
    return nifty_live_probe.snapshot()


@app.get("/v1/providers/upstox/diagnostic")
def upstox_diagnostic():
    """Safe read-only provider check. Never returns credentials or redirect URLs."""
    try:
        credentials = UpstoxCredentials.from_env()
    except RuntimeError:
        return {
            "provider": "upstox",
            "configured": False,
            "authenticated": False,
            "market_data_readable": False,
            "market_feed_authorized": False,
            "mode": "shadow",
            "detail": "analytics token is not configured",
        }

    client = UpstoxRestClient(UpstoxConfig(access_token=credentials.analytics_token))

    # Analytics-token authentication is proven with a documented read-only
    # market-data endpoint, not inferred from the websocket authorize helper.
    try:
        quote_payload = client.full_market_quote("NSE_INDEX|Nifty 50")
        quote_ok = str(quote_payload.get("status", "")).lower() == "success"
    except HTTPError as exc:
        upstox_error_code = None
        upstox_error_message = None
        try:
            import json
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            errors = body.get("errors") or []
            if errors and isinstance(errors[0], dict):
                upstox_error_code = None  # Do not echo untrusted provider bodies.
                upstox_error_message = "provider rejected request"
        except Exception:
            pass
        return {
            "provider": "upstox",
            "configured": True,
            "authenticated": False,
            "market_data_readable": False,
            "market_feed_authorized": False,
            "mode": "shadow",
            "http_status": exc.code,
            "upstox_error_code": upstox_error_code,
            "upstox_error_message": upstox_error_message,
            "detail": "Upstox rejected the read-only market-data probe",
        }
    except (URLError, TimeoutError):
        return {
            "provider": "upstox",
            "configured": True,
            "authenticated": False,
            "market_data_readable": False,
            "market_feed_authorized": False,
            "mode": "shadow",
            "detail": "Upstox could not be reached",
        }
    except Exception:
        return {
            "provider": "upstox",
            "configured": True,
            "authenticated": False,
            "market_data_readable": False,
            "market_feed_authorized": False,
            "mode": "shadow",
            "detail": "market-data diagnostic failed safely",
        }

    feed_authorized = False
    feed_http_status = None
    try:
        feed_payload = client.market_feed_authorize()
        feed_data = feed_payload.get("data") or {}
        feed_authorized = (
            str(feed_payload.get("status", "")).lower() == "success"
            and bool(feed_data.get("authorized_redirect_uri"))
        )
    except HTTPError as exc:
        feed_http_status = exc.code
    except Exception:
        pass

    return {
        "provider": "upstox",
        "configured": True,
        "authenticated": quote_ok,
        "market_data_readable": quote_ok,
        "market_feed_authorized": feed_authorized,
        "market_feed_authorize_http_status": feed_http_status,
        "mode": "shadow",
        "detail": (
            "analytics token authenticated for read-only market data"
            if quote_ok
            else "market-data response was incomplete"
        ),
    }
