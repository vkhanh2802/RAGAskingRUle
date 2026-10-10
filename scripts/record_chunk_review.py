import argparse
import csv
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bind visually checked chunk selections to validated hashes."
    )
    parser.add_argument(
        "--inventory", type=Path, default=Path("data/manifests/chunk_review_inventory.csv")
    )
    parser.add_argument(
        "--selection", type=Path, default=Path("data/manifests/chunk_review_selection.csv")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("data/manifests/structured_chunk_review.csv")
    )
    args = parser.parse_args()
    with args.inventory.open(encoding="utf-8", newline="") as file:
        inventory = {row["chunk_id"]: row for row in csv.DictReader(file)}
    with args.selection.open(encoding="utf-8", newline="") as file:
        selections = list(csv.DictReader(file))
    rows = []
    for selection in selections:
        row = inventory[selection["chunk_id"]]
        rows.append(
            {
                **row,
                "review_method": "assistant_source_text_and_layout_comparison",
                "review_note": selection["review_note"],
            }
        )
    if len(rows) < 30:
        raise ValueError("T2.2 requires at least 30 reviewed chunks")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Recorded {len(rows)} visually checked chunks with immutable content hashes")


if __name__ == "__main__":
    main()
