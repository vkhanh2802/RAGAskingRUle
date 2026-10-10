from regularag.ingestion.cleaner import clean_text_block


def test_clean_text_block_normalizes_noise_but_preserves_lines() -> None:
    text = "  Điều\u00a0 1.\r\nNội  dung\u200b\tquan trọng.\n\n\nBảng 1  "

    assert clean_text_block(text) == "Điều 1.\nNội dung quan trọng.\n\nBảng 1"
