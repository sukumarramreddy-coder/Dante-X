"""One-command certification. Missing evidence is gated, never silently passed."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from urllib.parse import urlencode, urlsplit
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
EXPECTED_ARCHIVE = "3e1d5e403340e7e6f53949a6aa3be08360d1296be40df6f2d8b1ae8afdf32eef"


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def archive_check(source, backup, expected=EXPECTED_ARCHIVE):
    from .historical_replay import load_archive
    if not source.is_file() or not backup.is_file():
        return "PENDING", "Archive or backup unavailable; supply --archive and --backup"
    before = digest(source)
    if before != digest(backup):
        return "GATED", "Source and backup SHA256 differ"
    if expected and before.lower() != expected.lower():
        return "GATED", "Archive differs from explicitly expected SHA256"
    sessions, rejected = load_archive(source)
    backup_sessions, backup_rejected = load_archive(backup)
    count = sum(len(rows) for instruments in sessions.values() for rows in instruments.values())
    if rejected or backup_rejected or len(sessions) != 90 or count != 67500 or sessions != backup_sessions:
        return "GATED", f"Archive coverage rejected: {len(sessions)} sessions, {count} accepted rows"
    if before != digest(source) or before != digest(backup):
        return "GATED", "Archive changed during inspection"
    return "CLEAN", f"90 paired sessions; 67500 rows; OHLC/provenance/minute coverage valid; SHA256 {before}"


def sink_probe():
    from .validation_recorder import ValidationRecorder, NoCredentialRedirect
    url, key = os.getenv("DANTEX_VALIDATION_REST_URL", ""), os.getenv("DANTEX_VALIDATION_REST_KEY", "")
    if not url or not key:
        return "PENDING", "Configure both external validation REST variables in backend environment"
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        return "GATED", "External sink URL must use HTTPS without embedded credentials/query"
    marker = "AUDIT_"+uuid4().hex
    row = {"recorded_at": datetime.now(timezone.utc).isoformat(), "state": "DIAGNOSTIC",
           "decision": {"status": "AUDIT_DIAGNOSTIC", "authorization": "NONE", "audit_id": marker},
           "family_counts": {}, "readiness": {}, "market_snapshot": {"audit_id": marker}, "source_sample_id": 0}
    with tempfile.TemporaryDirectory(prefix="dante-audit-") as directory:
        recorder = ValidationRecorder(str(Path(directory)/"probe.db"))
        recorder._external_write(row)
    query = urlencode({"select": "decision", "decision->>audit_id": "eq."+marker, "limit": "2"})
    request = urllib.request.Request(url.rstrip("/")+"?"+query,
        headers={"apikey": key, "Authorization": "Bearer "+key})
    with urllib.request.build_opener(NoCredentialRedirect()).open(request, timeout=8) as response:
        payload = json.loads(response.read(65536))
    if not isinstance(payload, list) or len(payload) != 1 or payload[0].get("decision") != row["decision"]:
        return "GATED", "External readback did not match unique diagnostic record"
    return "CLEAN", "Unique non-training diagnostic written and independently read back; restart survival still unproven"


def live_feed_probe():
    from .freshness import market_session
    if not os.getenv("UPSTOX_ANALYTICS_TOKEN"):
        return "PENDING", "Read-only Upstox token unavailable"
    if not market_session()["market_open"]:
        return "USER ACTION", "Repeat during market hours to verify fresh ticks for both indices"
    # Isolate SDK threads. Discard all SDK output so URLs/tokens cannot enter logs.
    code = (
        "import os,time; from dantex.providers.upstox_core_live import core_live_feed; "
        "core_live_feed.start(); deadline=time.monotonic()+20\n"
        "while time.monotonic()<deadline:\n"
        " s=core_live_feed.snapshot()\n"
        " if s['state']=='LIVE' and s['connected']: os._exit(0)\n"
        " time.sleep(.5)\n"
        "os._exit(2)\n"
    )
    try:
        result = subprocess.run([sys.executable, "-c", code], stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=25, check=False)
    except subprocess.TimeoutExpired:
        return "GATED", "Live feed probe timed out"
    return ("CLEAN" if result.returncode == 0 else "GATED"), "Bounded two-index live heartbeat/freshness probe"


def security_check(root):
    files = subprocess.run(["git", "-c", f"safe.directory={root.as_posix()}", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
                           cwd=root, capture_output=True, check=True).stdout.decode().split("\0")
    patterns = [r"sk-(?:proj-)?[A-Za-z0-9_-]{30,}", r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
                r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}"]
    secrets = [os.getenv(k) for k in ("OPENAI_API_KEY", "UPSTOX_ANALYTICS_TOKEN", "DANTEX_VALIDATION_REST_KEY")]
    found = []
    for name in files:
        if not name:
            continue
        if Path(name).name == ".env":
            found.append(name)
            continue
        path = root/name
        if not path.is_file() or path.stat().st_size > 2000000:
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        if any(re.search(pattern, content) for pattern in patterns) or any(secret and len(secret) > 15 and secret in content for secret in secrets):
            found.append(name)
    return ("GATED", "Potential credential exposure in: "+", ".join(found)) if found else (
        "CLEAN", "Tracked text scan passed (heuristic; not proof of full Git-history secrecy)")


def run_command(command, cwd, output, name):
    # Tests/builds never inherit live provider credentials or enable paid calls.
    env = dict(os.environ)
    for key in list(env):
        if key.startswith(("UPSTOX_", "DANTEX_", "OPENAI_")):
            env.pop(key)
    env["DANTEX_OPENAI_ENABLED"] = "false"
    env["DANTEX_VALIDATION_DB"] = str(output/(name+"-validation.db"))
    env["DANTEX_LEARNING_DB"] = str(output/(name+"-learning.db"))
    try:
        result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True,
                                errors="replace", timeout=1200, check=False)
        text = result.stdout+result.stderr
        # Redact known credentials defensively even though child env is scrubbed.
        for key in ("OPENAI_API_KEY", "UPSTOX_ANALYTICS_TOKEN", "DANTEX_VALIDATION_REST_KEY"):
            if os.getenv(key):
                text = text.replace(os.environ[key], "[REDACTED]")
        (output/(name+".log")).write_text(text, encoding="utf-8")
        return ("CLEAN" if result.returncode == 0 else "GATED"), f"exit {result.returncode}; {name}.log"
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "GATED", type(exc).__name__


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="Include archive, replay and configured external probes")
    parser.add_argument("--archive", type=Path, default=Path.home()/"Dante-X-Ingestion/data/dantex-history.sqlite3")
    parser.add_argument("--backup", type=Path, default=Path.home()/"Dante-X-Ingestion/data/dantex-history-BACKUP.sqlite3")
    parser.add_argument("--expected-sha256", default=EXPECTED_ARCHIVE)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    output = args.output or ROOT/"audit-results"/(datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"-"+uuid4().hex[:8])
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    def check(name, function, critical=True):
        try:
            state, detail = function()
        except Exception as exc:
            state, detail = "GATED", type(exc).__name__
        row = {"check": name, "status": state, "detail": detail, "critical": critical}
        rows.append(row)
        print(f"{name:34} {state:12} {detail}", flush=True)
    print("DANTE-X PRE-APP CERTIFICATION", flush=True)
    check("Credential scan", lambda: security_check(ROOT))
    engine = ROOT/"services/engine"
    check("Engine suite / safety / replay", lambda: run_command([sys.executable, "-m", "pytest", "-q", "--basetemp", str(output/"pytest-tmp")], engine, output, "engine-tests"))
    check("Engine lint", lambda: run_command([sys.executable, "-m", "ruff", "check", "."], engine, output, "engine-lint"))
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    pnpm = shutil.which("pnpm") or shutil.which("pnpm.cmd")
    manager = npm or pnpm
    for name, script in (("Web tests", "test"), ("Web typecheck", "lint"), ("Web production build", "build")):
        check(name, lambda script=script: run_command([manager, "run", script], ROOT/"apps/web", output, "web-"+script)
              if manager else ("GATED", "Install Node/npm and run npm ci in apps/web"))
    if args.full:
        check("Historical archive + backup", lambda: archive_check(args.archive, args.backup, args.expected_sha256))
        if rows[-1]["status"] == "CLEAN":
            from .historical_replay import run_replay
            def replay():
                report = run_replay(args.archive, output/"historical-replay")
                return ("CLEAN" if report["status"] == "COMPLETE" else "GATED"), f"{report['sessions']} sessions; descriptive index-only replay"
            check("Full historical replay", replay)
        else:
            check("Full historical replay", lambda: ("PENDING", "Requires clean archive"))
        check("External durable write/read", sink_probe)
        def provider():
            from .api import upstox_diagnostic
            result = upstox_diagnostic()
            if not result["configured"]:
                return "PENDING", "Set UPSTOX_ANALYTICS_TOKEN in backend environment"
            return ("CLEAN" if result["authenticated"] and result["market_feed_authorized"] else "GATED"), "Read-only auth/market-feed authorization probe"
        check("Upstox authentication", provider)
        check("Live feed freshness", live_feed_probe)
        check("External restart persistence", lambda: ("USER ACTION", "Read diagnostic record after a real deployment restart"))
        check("Live disconnect/reconnect", lambda: ("USER ACTION", "Perform controlled live disconnect and verify fail-closed recovery"))
    else:
        check("External certification", lambda: ("PENDING", "Run --full with local archive and external credentials"), False)
    failures = sum(row["critical"] and row["status"] == "GATED" for row in rows)
    pending = sum(row["critical"] and row["status"] in ("PENDING", "USER ACTION") for row in rows)
    final = "GATED" if failures or pending else ("CLEAN" if args.full else "OFFLINE_CHECKS_CLEAN")
    report = {"status": final, "critical_failures": failures, "critical_pending": pending, "checks": rows,
              "read_only": True, "auto_execution": False, "calibrated_probability": None}
    (output/"report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"FINAL: {final}; critical failures={failures}; critical pending={pending}", flush=True)
    return 1 if failures else 2 if pending else 0


if __name__ == "__main__":
    raise SystemExit(main())
