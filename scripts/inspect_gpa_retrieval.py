import argparse
import json
from dataclasses import asdict
from pathlib import Path

from regularag.core.config import Settings
from regularag.retrieval.config import RagBaselineConfig
from regularag.retrieval.embedding import SentenceTransformerEmbedder
from regularag.retrieval.filters import RetrievalFilters
from regularag.retrieval.keyword import KeywordRepository
from regularag.retrieval.pipeline import RetrievalPipeline
from regularag.retrieval.repository import PgVectorRepository


def main():
    parser = argparse.ArgumentParser(
        description="Inspect GPA query before/after freshness; no generator."
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    settings = Settings()
    config = RagBaselineConfig.from_path(settings.rag_config_path)
    embedder = SentenceTransformerEmbedder(config.embedding)
    dense = PgVectorRepository(settings, config)
    keyword = KeywordRepository(settings, config)
    pipeline = RetrievalPipeline(config, embedder, dense, keyword)
    query = (
        "Nếu điểm trung bình đến hiện tại của tôi >=8.0, "
        "tôi sẽ được phép đăng kí bao nhiêu tín chỉ?"
    )
    vector = embedder.embed_query(query)
    records = []
    for filters in (None, RetrievalFilters(document_ids=["uit_790_2022"])):
        raw = dense.search(vector, 20, filters)
        kw = keyword.search(query, 20, filters)
        pool = pipeline.candidates(query, "hybrid", filters)
        records.append(
            {
                "filters": filters.model_dump(mode="json") if filters else {},
                "dense_raw": [asdict(hit) for hit in raw],
                "keyword_raw": [asdict(hit) for hit in kw],
                "post_freshness": [asdict(hit) for hit in pool],
            }
        )
    pipeline.release_models()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    for record in records:
        target = next(
            (hit for hit in record["dense_raw"] if hit["chunk_id"] == "uit_790_2022:chunk:0020"),
            None,
        )
        print(
            json.dumps(
                {
                    "filters": record["filters"],
                    "target_dense_score": target["score"] if target else None,
                    "minimum_cosine": config.retrieval.minimum_score,
                    "target_retained_after_freshness": any(
                        hit["chunk_id"] == "uit_790_2022:chunk:0020"
                        for hit in record["post_freshness"]
                    ),
                    "freshness_failures": sorted(
                        {
                            hit["freshness_failure"]
                            for hit in record["post_freshness"]
                            if hit["freshness_failure"]
                        }
                    ),
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
