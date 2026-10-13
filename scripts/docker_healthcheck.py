import json
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


def main():
    try:
        with urlopen("http://127.0.0.1:8000/health", timeout=4) as response:
            payload = json.load(response)
        return 0 if payload.get("status") == "ok" else 1
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
