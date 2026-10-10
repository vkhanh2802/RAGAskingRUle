import json

from regularag.generation.llama import LlamaCppGenerator, build_answer_grammar
from tests.unit.generation.test_service import _config


def test_answer_schema_converts_with_the_installed_llama_cpp_grammar_engine() -> None:
    # Conversion catches unsupported JSON Schema syntax without loading a model.
    grammar = build_answer_grammar()

    assert grammar is not None


def test_request_scoped_passage_enum_converts_with_real_grammar_engine():
    assert build_answer_grammar(("P1", "P2", "P12")) is not None


def test_structural_retry_is_bounded_and_keeps_diagnostics():
    class Model:
        def __init__(self):
            self.outputs = iter(['{"passage_ids":["P1","P1"]}', '{"passage_ids":["P2"]}'])
            self.calls = 0

        def create_completion(self, **kwargs):
            self.calls += 1
            return {"choices": [{"text": next(self.outputs)}]}

    config = _config().generation
    config.response_policy = "verified_passages"
    generator = LlamaCppGenerator(config)
    generator._model = Model()
    generator._prompt_tokens = lambda prompt: [1] * 20
    result = generator.generate(
        json.dumps({"passages": [{"passage_id": "P1"}, {"passage_id": "P2"}]})
    )
    assert result.status == "answered" and result.passage_ids == ("P2",)
    assert result.attempts == 2 and len(result.raw_attempts) == 2
    assert generator._model.calls == 2
