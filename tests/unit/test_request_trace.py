import json
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Event
from time import sleep
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from regularag.core.config import Settings
from regularag.core.logging import JsonFormatter
from regularag.core.tracing import current_trace
from regularag.generation.local import GeneratedAnswer
from regularag.generation.service import AnswerService
from regularag.main import create_app
from tests.unit.generation.test_service import (
    FakeEmbedder,
    FakeGenerator,
    FakeRetriever,
    _chunk,
    _config,
)


class Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        if hasattr(record, "trace"):
            self.records.append(record)


@pytest.fixture
def traced_client():
    app = create_app(Settings(environment="test"))
    capture = Capture()
    logger = logging.getLogger("regularag.trace")
    logger.addHandler(capture)
    try:
        with TestClient(app) as client:
            yield app, client, capture
    finally:
        logger.removeHandler(capture)


def service(generator=None):
    config = _config()
    config.generation.response_policy = "verified_passages"
    return AnswerService(
        config,
        FakeEmbedder(),
        FakeRetriever([replace(_chunk(), text="Học kỳ hè tối đa12 tín chỉ.")]),
        generator
        or FakeGenerator(GeneratedAnswer("answered", "", (), "MODEL_CANARY", passage_ids=("P1",))),
    )


def test_request_id_reaches_sync_pipeline_response_and_log_without_copying_client_data(
    traced_client,
):
    app, client, capture = traced_client
    app.state.answer_service = service()
    response = client.post(
        "/api/v1/ask",
        json={"question": "Học kỳ hè tối đa bao nhiêu tín chỉ?"},
        headers={"X-Request-ID": "HEADER_CANARY", "Authorization": "AUTH_CANARY"},
    )
    assert response.status_code == 200
    identifier = response.headers["x-request-id"]
    assert str(UUID(identifier)) == identifier == response.json()["request_id"]
    assert len(capture.records) == 1
    record = capture.records[0]
    assert record.request_id == record.trace["request_id"] == identifier
    serialized = JsonFormatter().format(record)
    assert "CANARY" not in serialized
    assert record.trace["metadata"]["prompt_version"] == "test-prompt"
    assert record.trace["result"]["cited_passage_ids"] == ["P1"]
    assert current_trace() is None


@pytest.mark.parametrize("status", [422, 503, 500])
def test_validation_and_failed_requests_always_have_correlated_metadata_only_trace(
    traced_client, status
):
    app, client, capture = traced_client

    class Failing:
        def ask(self, *args, **kwargs):
            if status == 503:
                raise OSError("password=EXCEPTION_CANARY")
            raise KeyError("EXCEPTION_CANARY")

    app.state.answer_service = Failing()
    response = client.post(
        "/api/v1/ask",
        json={"question": "QUESTION_CANARY", **({"top_k": 100} if status == 422 else {})},
    )
    assert response.status_code == status
    identifier = response.headers["x-request-id"]
    assert capture.records[0].trace["request_id"] == identifier
    assert "CANARY" not in json.dumps(capture.records[0].trace)
    if status != 422:  # FastAPI's standard validation body may echo invalid input, not logs.
        assert "EXCEPTION_CANARY" not in response.text
    root = next(s for s in capture.records[0].trace["spans"] if s["name"] == "http.request")
    assert root["attributes"]["http_status"] == status


def test_concurrent_requests_keep_independent_traces_and_measure_the_inference_queue(traced_client):
    app, client, capture = traced_client
    second_entered = Event()
    entries = []

    class WaitingGenerator(FakeGenerator):
        def generate(self, prompt):
            assert second_entered.wait(5)
            sleep(0.03)
            return super().generate(prompt)

    class SignallingService(AnswerService):
        def ask(self, *args, **kwargs):
            entries.append(1)
            if len(entries) == 2:
                second_entered.set()
            return super().ask(*args, **kwargs)

    delegate = service(
        WaitingGenerator(GeneratedAnswer("answered", "", (), "", passage_ids=("P1",)))
    )
    app.state.answer_service = SignallingService(
        delegate.config, delegate.embedder, delegate.retriever, delegate.generator
    )
    with ThreadPoolExecutor(2) as executor:
        responses = list(
            executor.map(
                lambda _: client.post(
                    "/api/v1/ask", json={"question": "Học kỳ hè tối đa bao nhiêu tín chỉ?"}
                ),
                range(2),
            )
        )
    assert all(r.status_code == 200 for r in responses)
    identifiers = {r.headers["x-request-id"] for r in responses}
    assert len(identifiers) == 2 == len(capture.records)
    assert {record.trace["request_id"] for record in capture.records} == identifiers
    waits = [
        span["duration_ms"]
        for record in capture.records
        for span in record.trace["spans"]
        if span["name"] == "inference.queue"
    ]
    assert max(waits) >= 20


def test_trace_can_be_disabled_while_request_id_remains_available():
    app = create_app(Settings(environment="test", pipeline_tracing_enabled=False))
    app.state.answer_service = service()
    capture = Capture()
    logger = logging.getLogger("regularag.trace")
    logger.addHandler(capture)
    try:
        response = TestClient(app).post(
            "/api/v1/ask", json={"question": "Học kỳ hè tối đa bao nhiêu tín chỉ?"}
        )
        assert response.status_code == 200 and response.json()["request_id"]
        assert not capture.records
    finally:
        logger.removeHandler(capture)


def test_failed_trace_sink_does_not_turn_a_verified_answer_into_an_http_error(traced_client):
    app, client, _ = traced_client
    app.state.answer_service = service()

    class FailedSink(logging.Handler):
        def emit(self, record):
            raise OSError("sink unavailable")

    sink = FailedSink()
    logger = logging.getLogger("regularag.trace")
    logger.addHandler(sink)
    try:
        response = client.post(
            "/api/v1/ask", json={"question": "Học kỳ hè tối đa bao nhiêu tín chỉ?"}
        )
        assert response.status_code == 200 and response.json()["status"] == "answered"
    finally:
        logger.removeHandler(sink)
