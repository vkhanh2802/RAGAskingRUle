import re


class WordTokenizer:
    def __init__(self) -> None:
        self._token_to_id: dict[str, int] = {}
        self._id_to_token: dict[int, str] = {}

    def encode(self, text: str) -> list[int]:
        token_ids: list[int] = []
        for token in re.findall(r"\S+", text):
            if token not in self._token_to_id:
                token_id = len(self._token_to_id) + 1
                self._token_to_id[token] = token_id
                self._id_to_token[token_id] = token
            token_ids.append(self._token_to_id[token])
        return token_ids

    def decode(self, token_ids: list[int]) -> str:
        return " ".join(self._id_to_token[token_id] for token_id in token_ids)

    def count(self, text: str) -> int:
        return len(self.encode(text))
