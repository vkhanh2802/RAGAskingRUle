# RegulaRAG evaluation

Trong Conda `ragschool`, Docker/cache/corpus đã setup, chạy:

```powershell
python scripts/run_evaluation.py
```

Default chỉ60development từ `data/evaluation/v1/`; read-only pre/post-flight kiểm
freeze/corpus/quality/model/PDF hashes. Gold/reference/requiredfacts không gửi model.
Run mới ở `evals/results/<UTC-run-id>/`, Git ignored vì chứa source/model traces.
Mỗi run có config/commit/source fingerprint/hardware, predictions, retrieval/answer/
operational metrics vàsummary. Direct report ban đầu để semantic manualmetrics null;
offset/hash fidelity và status/retrieval/timing/tokens được tính tự động.

`review_packet.md` dùng đối chiếu actualanswer với required facts/locators/conditions.
Manual reviewJSON theo `AnswerReview` schema bind SHA của response; ghi coveredfactIDs,
faithful/relevant actual citedPIDs, forbiddenclaims vàbehaviour verdict. Re-score không
gọi model hoặc đổi predictions:

```powershell
python scripts/run_evaluation.py --score-only --run-dir evals/results/<run-id> --review <review.json>
```

Hoặc ghi decisionJSON gồm `predictions_sha256` của run và `reviews` keyed questionID;
mỗi row khai báo đầy đủ các trường chấm vànote/reviewer, không khai báo derived
questionID/responseSHA. Runner bind exact responses, không tự suy fact labels:

```powershell
python scripts/run_evaluation.py --score-only --run-dir evals/results/<run-id> --review-decisions <decisions.json>
python scripts/publish_evaluation_summary.py --run-dir evals/results/<run-id> --output data/manifests/<aggregate.json>
```

Publicpublisher chỉ xuất aggregate/config/ID-only metrics sau complete manualreview,
không raw answers/quotes/modeltraces. Run mới cầnreview mới; decisionSHA từrun cũ sẽ
bịreject. Baseline T4.2: `docs/evaluation-runner-review.md`,60reviewed cases vàfailures.

Recall@5/@10 vàMRR@10 dùng supportchunks trênexpectedanswered, không lấy contrast/
abstentioncontext làmgold. Rank10 quan sát cùngpool thực; answer giữ defaulttop-k và
context/tokenbudget. Không có gradedrelevance nên nDCG null/notapplicable.
Facts-spancoverage chỉproxy; semanticcorrectness cầnreview. Claimunit là complete
citedquoteblock, không chấm câu tùy ý; relevance/coverage khác text/hash fidelity.

`--retrieval-mode vector|keyword|hybrid`, `--no-reranker` dànhT4.3 fixed-corpus/LLM/
budget comparisons. `--split test` là explicit vàchỉ dùng sau khi chốtconfigcuối;
T4.2 chạydevelopment. `--limit` cho pilots, đượcghi rõ roster, không giả là fullrun.
Không overwrite runpath; predictions flush từngrequest, failure.json giữ technicalfailures.
