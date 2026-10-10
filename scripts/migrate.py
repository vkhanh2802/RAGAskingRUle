import argparse
import json
from dataclasses import asdict
from pathlib import Path

from regularag.core.config import get_settings
from regularag.db.migrations import apply_migrations


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply pending PostgreSQL migrations.")
    parser.add_argument(
        "--migrations-dir",
        type=Path,
        default=Path("scripts/db/migrations"),
    )
    args = parser.parse_args()
    result = apply_migrations(get_settings(), args.migrations_dir)
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()
