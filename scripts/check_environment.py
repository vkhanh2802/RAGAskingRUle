from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


def main() -> None:
    requirements = [
        line.strip().split("==", 1)
        for line in Path("requirements.lock").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith(("#", "--"))
    ]
    mismatches = []
    for name, expected in requirements:
        try:
            actual = version(name)
        except PackageNotFoundError:
            actual = "not installed"
        if actual != expected:
            mismatches.append(f"{name}: expected {expected}, found {actual}")
    print(f"Locked packages: {len(requirements)}; mismatches: {len(mismatches)}")
    for mismatch in mismatches:
        print(mismatch)
    if mismatches:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
