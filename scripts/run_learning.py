"""Start the local read-only engine with durable, isolated learning evidence."""
import argparse
import os
from pathlib import Path

import uvicorn
from dotenv import dotenv_values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--credentials-file", type=Path)
    parser.add_argument("--port", type=int, default=8010)
    args = parser.parse_args()
    data = args.data_dir.resolve()
    data.mkdir(parents=True, exist_ok=True)
    if args.credentials_file:
        values = dotenv_values(args.credentials_file)
        # Only provider credentials; don't inherit an external recorder/sink.
        for key in ("UPSTOX_ANALYTICS_TOKEN", "UPSTOX_ACCESS_TOKEN"):
            if values.get(key):
                os.environ[key] = values[key]
    os.environ["DANTEX_MODE"] = "shadow"
    os.environ["DANTEX_LEARNING_DB"] = str(data / "learning.sqlite3")
    os.environ["DANTEX_LEARNING_DURABLE"] = "true"
    os.environ["DANTEX_VALIDATION_DB"] = str(data / "validation.sqlite3")
    os.environ["DANTEX_VALIDATION_DURABLE"] = "true"
    for key in ("DANTEX_VALIDATION_REST_URL", "DANTEX_VALIDATION_REST_KEY"):
        os.environ.pop(key, None)
    uvicorn.run("dantex.api:app", host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
