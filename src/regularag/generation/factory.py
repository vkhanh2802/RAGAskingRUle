from regularag.core.config import Settings
from regularag.generation.llama import LlamaCppGenerator
from regularag.generation.local import TransformersGenerator
from regularag.generation.service import AnswerService
from regularag.retrieval.config import RagBaselineConfig
from regularag.retrieval.embedding import SentenceTransformerEmbedder
from regularag.retrieval.keyword import KeywordRepository
from regularag.retrieval.pipeline import RetrievalPipeline
from regularag.retrieval.repository import PgVectorRepository


def build_answer_service(
    settings: Settings, config: RagBaselineConfig | None = None
) -> AnswerService:
    config = config or RagBaselineConfig.from_path(settings.rag_config_path)
    embedder = SentenceTransformerEmbedder(config.embedding)
    repository = RetrievalPipeline(
        config, embedder, PgVectorRepository(settings, config), KeywordRepository(settings, config)
    )
    generator = (
        LlamaCppGenerator(config.generation)
        if config.generation.backend == "llama_cpp"
        else TransformersGenerator(config.generation)
    )
    return AnswerService(config, embedder, repository, generator)
