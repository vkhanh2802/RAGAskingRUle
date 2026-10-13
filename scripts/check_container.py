"""HTTP acceptance for packaged UI/API; real RAG checks are explicit development controls."""

import argparse
import json
from hashlib import sha256
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import UUID


def fetch(base, path, body=None):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body else None
    request = Request(
        base.rstrip("/") + path,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"} if body else {},
    )
    try:
        response = urlopen(request, timeout=180)
    except HTTPError as error:
        response = error
    with response:
        text = response.read().decode("utf-8")
        return response.status, {k.lower(): v for k, v in response.headers.items()}, text


def audit_answer(body):
    sources = {s["source_id"]: s for s in body["sources"]}
    cited = [p for p in body["evidence_passages"] if p["cited"]]
    for p in cited:
        source = sources[p["source_id"]]
        assert source["cited"] and source["chunk_id"] == p["chunk_id"]
        assert source["excerpt"][p["char_start"] : p["char_end"]] == p["text"]
        assert sha256(p["text"].encode()).hexdigest() == p["text_sha256"]
        views = source["evidence_char_ranges"]
        assert not views or any(a <= p["char_start"] < p["char_end"] <= b for a, b in views)
    assert body["answer"] == "\n\n".join(f"“{p['text']}” [{p['source_id']}]" for p in cited)


def main():
    parser = argparse.ArgumentParser(
        description="Check packaged health/UI/assets/guards; optionally real development RAG."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--real", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()
    if args.output_dir:
        args.output_dir.mkdir(parents=True)
    checks, rows = [], []

    def check(name, condition):
        assert condition, name
        checks.append(name)

    for path, kind in (
        ("/health", "health"),
        ("/", "html"),
        ("/assets/app.mjs", "javascript"),
        ("/api/v1/demo/catalog", "catalog"),
    ):
        status, headers, text = fetch(args.base_url, path)
        check(kind + " HTTP200", status == 200)
        if kind == "health":
            check("database/pgvector healthy", json.loads(text)["status"] == "ok")
        elif kind == "html":
            check("packaged Vietnamese UI", 'lang="vi"' in text and "Tra cứu bằng chứng" in text)
        elif kind == "javascript":
            check("packaged module MIME", "javascript" in headers.get("content-type", ""))
        else:
            catalog = json.loads(text)
            check(
                "final pipeline/catalog15",
                catalog["pipeline_version"] == "rag-obligation-support-v3"
                and len(catalog["documents"]) == 15,
            )
    cases = [
        (
            "D01",
            {"question": "Em chưa đạt chuẩn ngoại ngữ thì đăng ký bao nhiêu tín chỉ?"},
            "needs_clarification",
        ),
        ("D02", {"question": "Viết hàm Python quicksort."}, "insufficient_evidence"),
        ("D03", {"question": "Invalid top-k", "top_k": 999}, "validation"),
    ]
    if args.real:
        cases += [
            ("R01", {"question": "Theo1393 học kỳ hè tối đa bao nhiêu tín chỉ?"}, "answered"),
            (
                "R02",
                {
                    "question": "Nếu điểm trung bình đến hiện tại của tôi >=8.0, "
                    "tôi sẽ được phép đăng kí bao nhiêu tín chỉ?"
                },
                "answered",
            ),
            (
                "R03",
                {
                    "question": "Theo790 lớp đại cương tối thiểu bao nhiêu sinh viên?",
                    "filters": {"document_ids": ["uit_790_2022"]},
                },
                "insufficient_evidence",
            ),
        ]
    for case_id, request, expected in cases:
        status, headers, text = fetch(args.base_url, "/api/v1/ask", request)
        body = json.loads(text)
        identifier = headers.get("x-request-id")
        check(case_id + " request ID", str(UUID(identifier)) == identifier)
        check(
            case_id + " status",
            status == (422 if expected == "validation" else 200)
            and (expected == "validation" or body["status"] == expected),
        )
        if status == 200:
            check(case_id + " body/header correlation", body["request_id"] == identifier)
        if case_id == "D01":
            check(
                "clarification axes", "study_progress" in body["clarification"]["required_fields"]
            )
        if case_id == "R01":
            check(
                "real updated summer12",
                "12 tín chỉ" in body["answer"]
                and any(
                    s["document_id"] == "uit_1393_2023" and s["cited"] for s in body["sources"]
                ),
            )
        if case_id == "R02":
            check(
                "real unchanged GPA30/mainsemester",
                "30 tín chỉ" in body["answer"]
                and "học kỳ chính" in body["answer"]
                and any(s["document_id"] == "uit_790_2022" and s["cited"] for s in body["sources"]),
            )
        if case_id == "R03":
            check(
                "caller old-only filter/latest gate",
                body["applied_filters"]["document_ids"] == ["uit_790_2022"]
                and body["failure_reason"] == "latest_excluded_by_filters",
            )
        if body.get("status") == "answered":
            audit_answer(body)
            checks.append(case_id + " bound source/span/render fidelity")
        if args.output_dir:
            (args.output_dir / f"{case_id}-response.json").write_text(
                json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        rows.append(
            {
                "case_id": case_id,
                "http_status": status,
                "status": body.get("status"),
                "request_id": identifier,
                "failure_reason": body.get("failure_reason"),
            }
        )
    result = {
        "passed": True,
        "base_url": args.base_url,
        "real_development_rag": args.real,
        "assertions": checks,
        "cases": rows,
        "held_out_inference_requests": 0,
        "conditions": "Packaged startup/UI/trace/guard checks and optional development-only RAG. "
        "No held-out inference or claim of general accuracy; raw responses ignored.",
    }
    if args.summary:
        with args.summary.open("x", encoding="utf-8") as file:
            json.dump(result, file, ensure_ascii=False, indent=2)
            file.write("\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
