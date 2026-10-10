from typing import Protocol

from transformers import AutoTokenizer, PreTrainedTokenizerBase


class TextTokenizer(Protocol):
    def encode(self, text: str) -> list[int]: ...

    def decode(self, token_ids: list[int]) -> str: ...

    def count(self, text: str) -> int: ...


class HuggingFaceTokenizer:
    def __init__(self, model_name: str, revision: str) -> None:
        self.model_name = model_name
        self.revision = revision
        self._tokenizer: PreTrainedTokenizerBase = AutoTokenizer.from_pretrained(
            model_name,
            revision=revision,
            use_fast=True,
        )

    def encode(self, text: str) -> list[int]:
        return self._tokenizer.encode(text, add_special_tokens=False)

    def decode(self, token_ids: list[int]) -> str:
        return self._tokenizer.decode(
            token_ids,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )

    def count(self, text: str) -> int:
        return len(self.encode(text))
