from dataclasses import asdict
from time import perf_counter

from regularag.retrieval.freshness import select_with_updates


class TimedReranker:
    def __init__(self, delegate):
        self.delegate = delegate
        self.elapsed_ms = 0.0

    def rerank(self, question, chunks):
        started = perf_counter()
        try:
            return self.delegate.rerank(question, chunks)
        finally:
            self.elapsed_ms += (perf_counter() - started) * 1000

    def release(self):
        release = getattr(self.delegate, "release", None)
        if callable(release):
            release()


class RecordingRetriever:
    """Observe the real ranked pool; answer top-k/context/budget remain unchanged."""

    def __init__(self, pipeline):
        self.pipeline = pipeline
        self.reranker = TimedReranker(pipeline.reranker) if pipeline.reranker else None
        if self.reranker:
            pipeline.reranker = self.reranker
        self.reset()

    def reset(self):
        self.hits = []
        self.elapsed_ms = 0.0
        self.called = False
        if self.reranker:
            self.reranker.elapsed_ms = 0.0

    def search(self, question, limit, mode=None, filters=None):
        if not 1 <= limit <= 20:
            raise ValueError("Invalid top-k")
        self.called = True
        started = perf_counter()
        try:
            pool = self.pipeline.ranked_candidates(question, mode, filters)
            select = (
                select_with_updates
                if self.pipeline.freshness is not None
                else lambda chunks, k: chunks[:k]
            )
            self.hits = [asdict(hit) for hit in select(pool, 10)]
            return select(pool, limit)
        finally:
            self.elapsed_ms = (perf_counter() - started) * 1000

    def release_models(self):
        self.pipeline.release_models()

    @property
    def timings(self):
        rerank = self.reranker.elapsed_ms if self.reranker else 0.0
        return {
            "retrieval_called": self.called,
            "retrieval_ms": round(max(0.0, self.elapsed_ms - rerank), 3),
            "reranker_ms": round(rerank, 3),
        }


class RecordingGenerator:
    def __init__(self, delegate):
        self.delegate = delegate
        self.reset()

    def reset(self):
        self.output = None
        self.elapsed_ms = 0.0
        self.called = False

    @property
    def input_token_limit(self):
        return self.delegate.input_token_limit

    def count_prompt_tokens(self, prompt):
        return self.delegate.count_prompt_tokens(prompt)

    def generate(self, prompt):
        self.called = True
        started = perf_counter()
        try:
            self.output = self.delegate.generate(prompt)
            return self.output
        finally:
            self.elapsed_ms = (perf_counter() - started) * 1000

    def release(self):
        release = getattr(self.delegate, "release", None)
        if callable(release):
            release()
