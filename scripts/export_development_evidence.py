"""Export approved indexed evidence for local manual development-set review."""

import argparse
from pathlib import Path
from textwrap import fill

import psycopg
from psycopg.rows import dict_row

from regularag.core.config import get_settings
from regularag.retrieval.config import RagBaselineConfig
from regularag.retrieval.sql import READY_FILTER, retrieval_parameters


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/rag/baseline.json"))
    parser.add_argument("--document-id", action="append", default=[])
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/processed/development-evidence")
    )
    args = parser.parse_args()
    settings = get_settings()
    config = RagBaselineConfig.from_path(args.config)
    with psycopg.connect(str(settings.database_url), row_factory=dict_row) as connection:
        rows = connection.execute(
            f"""
            SELECT c.chunk_id, c.document_id, c.text, c.content_sha256,
                   c.pdf_page_start, c.pdf_page_end, c.article, c.clauses,
                   d.document_number, d.source_sha256
            FROM chunks c JOIN documents d ON d.document_id = c.document_id
            WHERE {READY_FILTER}
              AND (%(ids)s::text[] = '{{}}' OR d.document_id = ANY(%(ids)s))
            ORDER BY c.document_id, c.chunk_index
            """,
            {**retrieval_parameters(config), "ids": args.document_id},
        ).fetchall()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    documents = {}
    for row in rows:
        lines = documents.setdefault(row["document_id"], [])
        lines.extend(
            [
                f"## {row['chunk_id']}",
                f"Source: {row['document_number']} / {row['source_sha256']}",
                f"Content SHA256: {row['content_sha256']}",
                f"PDF: {row['pdf_page_start']}-{row['pdf_page_end']}; "
                f"article: {row['article']}; clauses: {row['clauses']}",
                "",
            ]
        )
        lines.extend(fill(line, width=100) for line in row["text"].splitlines())
        lines.extend(["", "---", ""])
    for document_id, lines in documents.items():
        (args.output_dir / f"{document_id}.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Exported {len(rows)} approved chunks across {len(documents)} documents")


if __name__ == "__main__":
    main()
