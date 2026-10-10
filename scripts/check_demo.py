import argparse
import json
import os
import subprocess
from pathlib import Path
from threading import Thread
from time import monotonic, sleep

import uvicorn

from regularag.core.config import Settings
from regularag.main import create_app


def main():
    parser = argparse.ArgumentParser(
        description="Browser QA against a temporary local demo server."
    )
    parser.add_argument("--real", action="store_true")
    parser.add_argument("--port", type=int, default=8767)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    server = uvicorn.Server(
        uvicorn.Config(
            create_app(Settings()), host="127.0.0.1", port=args.port, log_level="warning"
        )
    )
    thread = Thread(target=server.run, daemon=True)
    thread.start()
    try:
        deadline = monotonic() + 15
        while not server.started:
            if not thread.is_alive() or monotonic() > deadline:
                raise RuntimeError("Demo HTTP server did not start")
            sleep(0.1)
        env = {
            **os.environ,
            "DEMO_BASE_URL": f"http://127.0.0.1:{args.port}",
            "DEMO_OUTPUT_DIR": str(args.output_dir.resolve()),
            "DEMO_REAL": "1" if args.real else "0",
        }
        process = subprocess.run(
            ["node", "scripts/check_demo_browser.cjs"], env=env, timeout=900, check=False
        )
        report = json.loads((args.output_dir / "browser-report.json").read_text(encoding="utf-8"))
        report["held_out_inference_requests"] = 0
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        if process.returncode or not report["passed"]:
            raise SystemExit(1)
    finally:
        server.should_exit = True
        thread.join(timeout=15)


if __name__ == "__main__":
    main()
