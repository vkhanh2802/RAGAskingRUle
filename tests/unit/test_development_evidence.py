from copy import deepcopy

import pytest

from regularag.evaluation.development import verify_evidence


@pytest.mark.parametrize("field", ["content_sha256", "source_sha256", "source_pdf_pages"])
def test_changed_evidence_cannot_silently_keep_an_old_development_label(field):
    original = {
        "chunk": {"content_sha256": "a" * 64, "source_sha256": "b" * 64, "source_pdf_pages": [2]}
    }
    changed = deepcopy(original)
    changed["chunk"][field] = [3] if field == "source_pdf_pages" else "c" * 64
    with pytest.raises(ValueError, match="Stale"):
        verify_evidence(original, changed)
