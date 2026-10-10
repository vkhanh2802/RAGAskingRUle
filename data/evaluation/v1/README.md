# RegulaRAG evaluation100 v1

- 100 cases: D01–D60 development; T01–T40 prospective question/rule-family test.
- Category counts: 30 single clause /20multi /15scope /15no answer /10clarification /10adversarial.
- Expected statuses:75answered /15insufficient /10clarification. These are gold labels, not model results.
- 72 curated evidence spans/49approvedchunks, explicit PDF ranges/locators/excerpts/hashes.
- Frozen legacy30 queries/answers/filters/19goldchunks are preserved in development.
- `freeze.json` protects labels, evidence, reviews and authoring/exposure mapping.

Use `load_evaluation_cases(directory)` for development by default. Test selection is
explicit. `python scripts/validate_evaluation_dataset.py` checks live source integrity
without embedding/reranking/generation. Rebuilding or refreezing this version is rejected.

Review is assistant source/behaviour review using inherited M2 source/page-quality evidence;
not independent human review. The corpus is shared, not document-disjoint. No held-out
RAG inference occurred during T4.1 construction. Freeze does not prove future model accuracy.

Report and usage: `docs/evaluation-dataset-review.md`.
