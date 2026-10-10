import json
from datetime import UTC, datetime

from regularag.evaluation.dataset import canonical_hash
from regularag.evaluation.integrity import verify_live_dataset
from regularag.evaluation.metrics import EVALUATOR_VERSION, citation_binding
from regularag.evaluation.runner import rescore, run_evaluation, runtime_metadata, write_json
from regularag.retrieval.config import RagBaselineConfig

VARIANTS = {
    "vector_only": ("vector", False),
    "keyword_only": ("keyword", False),
    "hybrid_rrf": ("hybrid", False),
    "hybrid_reranked": ("hybrid", True),
}
SELECTION_RULE = "Integrity gates, then complete answer correctness, required fact recall, "
SELECTION_RULE += "task-support citation precision, lower end-to-end p95 then p50; development only"


def variant_config(base, variant, top_k=None):
    if variant not in VARIANTS:
        raise ValueError("Unknown ablation variant")
    config = base.model_copy(deep=True)
    config.retrieval.mode, config.reranker.enabled = VARIANTS[variant]
    if top_k is not None:
        if type(top_k) is not int or not 1 <= top_k <= 20:
            raise ValueError("Invalid top-k")
        config.retrieval.top_k = top_k
    return config


def fixed_config_hash(config, allow_top_k=False):
    value = config.model_dump(mode="json")
    value["retrieval"].pop("mode")
    value["reranker"].pop("enabled")
    if allow_top_k:
        value["retrieval"].pop("top_k")
    return canonical_hash(value)


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def predictions_at(directory):
    return [
        json.loads(line)
        for line in (directory / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
    ]


def prepare_matrix(root, dataset, settings, base):
    cases, _, _, lock = verify_live_dataset(dataset, settings, base)
    development = [case for case in cases if case.split == "development"]
    runtime = runtime_metadata(base, lock, "development", development)
    signature = {
        "base_config_sha256": canonical_hash(base.model_dump(mode="json")),
        "dataset_sha256": lock["dataset_sha256"],
        "corpus_sha256": lock["corpus_sha256"],
        "runtime_source_sha256": runtime["runtime_source_sha256"],
        "hardware": runtime["hardware"],
        "packages": runtime["packages"],
        "concurrency": runtime["concurrency"],
        "question_ids": [case.question_id for case in development],
    }
    if (root / "matrix.json").exists():
        matrix = load_json(root / "matrix.json")
        if any(matrix[key] != value for key, value in signature.items()):
            raise ValueError("Ablation base/source/corpus/roster drift; create a new matrix")
        return matrix
    if root.exists():
        raise ValueError("Unrecognised existing matrix directory")
    root.mkdir(parents=True)
    matrix = {
        **signature,
        "created_at": datetime.now(UTC).isoformat(),
        "base_config": base.model_dump(mode="json"),
        "selection_rule": SELECTION_RULE,
        "conditions": "Serial fresh Python process per variant; same case order; no warmup; "
        "per-request low-memory reload and OS/HF caches. Single pass, "
        "not causal latency attribution.",
        "jobs": {},
    }
    write_json(root / "matrix.json", matrix)
    return matrix


def run_variant(root, dataset, settings, base, variant, top_k=None):
    matrix = prepare_matrix(root, dataset, settings, base)
    config = variant_config(base, variant, top_k)
    label = (
        variant
        if config.retrieval.top_k == base.retrieval.top_k
        else (f"{variant}_k{config.retrieval.top_k}")
    )
    if label in matrix["jobs"]:
        raise ValueError("Ablation job already registered; preserve its artifacts")
    job = {
        "variant": variant,
        "top_k": config.retrieval.top_k,
        "config": config.model_dump(mode="json"),
        "config_sha256": canonical_hash(config.model_dump(mode="json")),
    }
    matrix["jobs"][label] = job
    write_json(root / "matrix.json", matrix)
    result = run_evaluation(settings, config, dataset, root / label)
    return {"label": label, **result}


def validated_jobs(root, dataset, settings, labels):
    matrix = load_json(root / "matrix.json")
    base = RagBaselineConfig.model_validate(matrix["base_config"])
    cases, evidence, chunks, lock = verify_live_dataset(dataset, settings, base)
    if lock["dataset_sha256"] != matrix["dataset_sha256"]:
        raise ValueError("Matrix gold drift")
    jobs = {}
    for label in labels:
        registered = matrix["jobs"][label]
        directory = root / label
        metadata = load_json(directory / "config.json")
        predictions = predictions_at(directory)
        config = RagBaselineConfig.model_validate(registered["config"])
        if (
            metadata["state"] != "completed"
            or not metadata["postflight_integrity"]
            or metadata["split"] != "development"
            or metadata["held_out_inference_requests"] != 0
            or metadata["evaluator_version"] != EVALUATOR_VERSION
            or metadata["config_sha256"] != registered["config_sha256"]
            or canonical_hash(config.model_dump(mode="json")) != registered["config_sha256"]
            or metadata["config"] != registered["config"]
            or metadata["dataset_sha256"] != matrix["dataset_sha256"]
            or metadata["corpus_sha256"] != matrix["corpus_sha256"]
            or metadata["runtime_source_sha256"] != matrix["runtime_source_sha256"]
            or metadata["hardware"] != matrix["hardware"]
            or metadata["packages"] != matrix["packages"]
            or metadata["concurrency"] != matrix["concurrency"]
            or metadata["question_ids"] != matrix["question_ids"]
            or [p["question_id"] for p in predictions] != matrix["question_ids"]
            or canonical_hash(predictions) != metadata["predictions_sha256"]
        ):
            raise ValueError("Incompatible, incomplete or altered ablation run: " + label)
        for case, prediction in zip(
            [c for c in cases if c.split == "development"], predictions, strict=True
        ):
            request = {
                "question": case.question,
                "filters": case.filters.model_dump(mode="json"),
                "scope": case.scope.model_dump(mode="json"),
            }
            if prediction["request"] != request or prediction["split"] != "development":
                raise ValueError("Query/filter/scope drift across variants")
            if not citation_binding(prediction["response"], chunks)["fidelity"]:
                raise ValueError("Ablation citation integrity gate failed")
        jobs[label] = {"config": config, "metadata": metadata, "predictions": predictions}
    return matrix, cases, evidence, chunks, jobs


def semantic_bundle(prediction):
    """Group only identical claims/scope/source semantics, not merely same status or chunk hit."""
    response = prediction["response"]
    sources = {source["source_id"]: source for source in response.get("sources", [])}
    claims = []
    for p in response.get("evidence_passages", []):
        if not p["cited"]:
            continue
        source = sources[p["source_id"]]
        identity = {
            key: source.get(key)
            for key in (
                "document_id",
                "document_number",
                "source_url",
                "article",
                "clauses",
                "pdf_page_start",
                "pdf_page_end",
                "legal_status",
                "applies_to",
                "cohort_scope",
                "cohort_from",
                "cohort_to",
                "effective_from_date",
                "effective_to_date",
                "freshness_status",
                "required_update_chunk_ids",
                "evidence_char_ranges",
            )
        }
        claims.append(
            {
                "chunk_id": p["chunk_id"],
                "char_start": p["char_start"],
                "char_end": p["char_end"],
                "text": p["text"],
                "text_sha256": p["text_sha256"],
                "source": identity,
                "passage_id": p["passage_id"],
            }
        )
    claims.sort(key=lambda c: (c["chunk_id"], c["char_start"], c["char_end"], c["text_sha256"]))
    semantic = {
        "request": prediction["request"],
        "status": response.get("status"),
        "failure_reason": response.get("failure_reason"),
        "applied_filters": response.get("applied_filters"),
        "resolved_scope": response.get("resolved_scope"),
        "clarification": response.get("clarification"),
        "non_answer_text": response.get("answer") if response.get("status") != "answered" else None,
        "claims": [
            {key: value for key, value in claim.items() if key != "passage_id"} for claim in claims
        ],
    }
    return canonical_hash(semantic), claims


def review_groups(jobs):
    groups = {}
    for label, job in jobs.items():
        for p in job["predictions"]:
            digest, claims = semantic_bundle(p)
            key = p["question_id"] + "/" + digest[:12]
            group = groups.setdefault(
                key,
                {
                    "question_id": p["question_id"],
                    "semantic_sha256": digest,
                    "claims": claims,
                    "members": {},
                    "response": p["response"],
                },
            )
            if group["semantic_sha256"] != digest:
                raise ValueError("Review group hash collision")
            group["members"][label] = {
                "response_sha256": canonical_hash(p["response"]),
                "claim_to_passage": {f"C{i}": c["passage_id"] for i, c in enumerate(claims, 1)},
            }
    return groups


def groups_signature(groups):
    return canonical_hash(
        {
            key: {"semantic_sha256": g["semantic_sha256"], "members": g["members"]}
            for key, g in groups.items()
        }
    )


def export_matrix_review(root, dataset, settings, labels):
    _, cases, _, _, jobs = validated_jobs(root, dataset, settings, labels)
    groups = review_groups(jobs)
    signature = groups_signature(groups)
    lines = [
        "# Ablation actual-output review",
        "Review groups SHA: " + signature,
        "Identical quote/source/scope groups only; new hashes/PID mappings for every run.",
    ]
    lookup = {case.question_id: case for case in cases}
    for key in sorted(groups):
        group = groups[key]
        case = lookup[group["question_id"]]
        response = group["response"]
        lines.extend(
            [
                "",
                "## " + key,
                "Variants: " + ", ".join(group["members"]),
                case.question,
                "Expected: " + case.expected_status,
                "Actual: "
                + str(response.get("status"))
                + "/"
                + str(response.get("failure_reason")),
                *[f"- {f.fact_id}: {f.statement}" for f in case.required_facts],
                "Required fields: " + ", ".join(case.required_clarifications),
                "Forbidden: " + "; ".join(case.must_not_claim),
            ]
        )
        if not group["claims"]:
            lines.append(response.get("answer", ""))
        for i, claim in enumerate(group["claims"], 1):
            lines.extend(
                [
                    f"### C{i}: {claim['chunk_id']} {claim['char_start']}:{claim['char_end']}",
                    claim["text"],
                ]
            )
    (root / "review_packet.md").write_text("\n\n".join(lines), encoding="utf-8")
    write_json(root / "review_groups.json", {"signature": signature, "groups": groups})
    return {
        "groups_sha256": signature,
        "unique_question_outputs": len(groups),
        "predictions": sum(len(j["predictions"]) for j in jobs.values()),
    }


def apply_matrix_reviews(root, dataset, settings, labels, decisions_path):
    _, _, _, _, jobs = validated_jobs(root, dataset, settings, labels)
    groups = review_groups(jobs)
    decisions = load_json(decisions_path)
    if decisions["groups_sha256"] != groups_signature(groups) or set(decisions["reviews"]) != set(
        groups
    ):
        raise ValueError("Manual group reviews incomplete or bound to different predictions")
    rows = {label: [] for label in labels}
    for key, group in groups.items():
        review = decisions["reviews"][key]
        for label, member in group["members"].items():
            mapping = member["claim_to_passage"]
            for field in ("faithful_claim_ids", "relevant_claim_ids"):
                ids = review[field]
                if len(ids) != len(set(ids)) or not set(ids).issubset(mapping):
                    raise ValueError("Unknown/duplicate manual claim identifier")
            rows[label].append(
                {
                    "question_id": group["question_id"],
                    "response_sha256": member["response_sha256"],
                    "covered_fact_ids": review["covered_fact_ids"],
                    "faithful_passage_ids": [mapping[c] for c in review["faithful_claim_ids"]],
                    "relevant_passage_ids": [mapping[c] for c in review["relevant_claim_ids"]],
                    "forbidden_claims_present": review["forbidden_claims_present"],
                    "behaviour_correct": review["behaviour_correct"],
                    "reviewer": review["reviewer"],
                    "note": review["note"],
                }
            )
    for label, values in rows.items():
        path = root / label / "group_bound_reviews.json"
        write_json(path, sorted(values, key=lambda r: r["question_id"]))
        rescore(settings, jobs[label]["config"], dataset, root / label, review_path=path)
    return {
        "reviewed_predictions": sum(len(values) for values in rows.values()),
        "reviewed_groups": len(groups),
    }


def selection_key(row):
    def value(metric):
        return metric["value"] if metric["value"] is not None else -1.0

    return (
        -value(row["answer"]["correctness"]),
        -value(row["answer"]["required_fact_recall"]),
        -value(row["answer"]["citation_support_precision"]),
        row["operations"]["stages"]["end_to_end_ms"]["p95"],
        row["operations"]["stages"]["end_to_end_ms"]["p50"],
        row["label"],
    )


def compare_matrix(root, dataset, settings, labels, allow_top_k=False):
    matrix, _, _, _, jobs = validated_jobs(root, dataset, settings, labels)
    hashes = {fixed_config_hash(job["config"], allow_top_k) for job in jobs.values()}
    if len(hashes) != 1:
        raise ValueError(
            "Uncontrolled LLM/prompt/budget/candidate/filter configuration differences"
        )
    rows = []
    scores = {}
    for label, job in jobs.items():
        directory = root / label
        review = directory / "answer_reviews.json"
        if not review.exists():
            raise ValueError("Comparison needs complete actual-answer review: " + label)
        rescore(settings, job["config"], dataset, directory, review_path=review)
        answer = load_json(directory / "answer_metrics.json")
        if answer["overall"]["reviewed"] != len(matrix["question_ids"]):
            raise ValueError("Comparison cannot drop unreviewed/failed cases")
        retrieval = load_json(directory / "retrieval_metrics.json")
        operations = load_json(directory / "operational_metrics.json")
        rows.append(
            {
                "label": label,
                "config_sha256": job["metadata"]["config_sha256"],
                "predictions_sha256": job["metadata"]["predictions_sha256"],
                "review_sha256": answer["review_sha256"],
                "config": job["config"].model_dump(mode="json"),
                "hardware": job["metadata"]["hardware"],
                "started_at": job["metadata"]["started_at"],
                "finished_at": job["metadata"]["finished_at"],
                "retrieval": retrieval["overall"],
                "answer": answer["overall"],
                "operations": operations,
                "by_category": answer["by_category"],
            }
        )
        scores[label] = {r["question_id"]: r for r in answer["per_case"]}
    for row in rows:
        if (
            row["answer"]["filter_preservation"]["value"] != 1
            or row["answer"]["citation_fidelity"]["value"] != 1
        ):
            raise ValueError("Candidate fails hard evidence/filter gates")
    order = sorted(rows, key=selection_key)
    pairs = []
    for i, left in enumerate(labels):
        for right in labels[i + 1 :]:
            wins = [
                qid
                for qid in matrix["question_ids"]
                if scores[right][qid]["correct"] is True
                and scores[left][qid]["correct"] is not True
            ]
            losses = [
                qid
                for qid in matrix["question_ids"]
                if scores[left][qid]["correct"] is True
                and scores[right][qid]["correct"] is not True
            ]
            pairs.append({"left": left, "right": right, "right_wins": wins, "right_losses": losses})
    return {
        "matrix_root": root.as_posix(),
        "dataset_sha256": matrix["dataset_sha256"],
        "corpus_sha256": matrix["corpus_sha256"],
        "runtime_source_sha256": matrix["runtime_source_sha256"],
        "selection_rule": SELECTION_RULE,
        "selected_label": order[0]["label"],
        "variants": rows,
        "paired_correctness": pairs,
        "held_out_inference_requests": 0,
        "conditions": matrix["conditions"],
    }
