import argparse
import json
from pathlib import Path
from threading import Thread
from time import monotonic, sleep

import httpx
import uvicorn

from regularag.core.config import Settings
from regularag.main import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test a real temporary Uvicorn HTTP server.")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--question",
        default="Thời gian thực hiện KLTN thông thường là mấy học kỳ chính và bao nhiêu tuần?",
    )
    parser.add_argument("--output", type=Path, default=Path("data/processed/rag-http-smoke.json"))
    args = parser.parse_args()
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
                raise RuntimeError("Uvicorn did not start")
            sleep(0.1)
        with httpx.Client(base_url=f"http://127.0.0.1:{args.port}", timeout=300) as client:
            health = client.get("/health")
            health.raise_for_status()
            response = client.post("/api/v1/ask", json={"question": args.question})
            response.raise_for_status()
        payload = {
            "health_http_status": health.status_code,
            "health": health.json(),
            "ask_http_status": response.status_code,
            "question": args.question,
            "response": response.json(),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(
            json.dumps(
                {
                    "health_http_status": health.status_code,
                    "ask_http_status": response.status_code,
                    "status": response.json()["status"],
                    "answer": response.json()["answer"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        server.should_exit = True
        thread.join(timeout=15)


if __name__ == "__main__":
    main()
