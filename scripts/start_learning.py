"""Start local learner/dashboard without changing Windows execution policies."""
import argparse
import json
import os
import socket
import subprocess
from pathlib import Path
from urllib.request import urlopen


def listening(port):
    with socket.socket() as sock:
        sock.settimeout(1)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", required=True)
    parser.add_argument("--node", required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--credentials-file", type=Path)
    parser.add_argument("--engine-port", type=int, default=8010)
    parser.add_argument("--web-port", type=int, default=3010)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    data = args.data_dir.resolve()
    data.mkdir(parents=True, exist_ok=True)
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

    def launch(name, command, cwd, env=None):
        with (data / f"{name}.log").open("ab") as out, (data / f"{name}-error.log").open("ab") as err:
            child = subprocess.Popen(command, cwd=cwd, env=env, stdout=out, stderr=err,
                                     creationflags=flags, start_new_session=os.name != "nt")
        (data / f"{name}.pid").write_text(str(child.pid), encoding="utf-8")

    if listening(args.engine_port):
        with urlopen(f"http://127.0.0.1:{args.engine_port}/v1/calibration/learning", timeout=5) as response:
            if json.load(response).get("version") != "learning-30-v1":
                raise RuntimeError("engine port belongs to another service")
    else:
        command = [args.python, str(repo / "scripts/run_learning.py"), "--data-dir", str(data), "--port", str(args.engine_port)]
        if args.credentials_file:
            command += ["--credentials-file", str(args.credentials_file)]
        launch("engine", command, repo)
    if not listening(args.web_port):
        env = {**os.environ, "DANTEX_ENGINE_URL": f"http://127.0.0.1:{args.engine_port}"}
        web = repo / "apps/web"
        launch("web", [args.node, str(web / "node_modules/next/dist/bin/next"), "start", "-H", "127.0.0.1", "-p", str(args.web_port)], web, env)


if __name__ == "__main__":
    main()
