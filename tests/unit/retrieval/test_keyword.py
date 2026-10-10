from regularag.retrieval.keyword import build_keyword_query, normalize_vietnamese


def test_accented_and_unaccented_queries_have_the_same_terms_and_references() -> None:
    accented = build_keyword_query(
        "Theo Quyết định số 1393/QĐ-ĐHCNTT, Điều 1 học kỳ hè tối đa 12 tín chỉ?"
    )
    plain = build_keyword_query(
        "Theo Quyet dinh so 1393/QD-DHCNTT, Dieu 1 hoc ky he toi da 12 tin chi?"
    )

    assert accented.tsquery == plain.tsquery
    assert accented.document_codes == plain.document_codes == ("1393",)
    assert accented.articles == plain.articles == ("1",)
    assert normalize_vietnamese("Đăng ký HỌC LẠI") == "dang ky hoc lai"


def test_query_operators_are_not_accepted_as_user_supplied_tsquery_syntax() -> None:
    query = build_keyword_query("học lại | ! điểm & 'foo' <-> bar")

    assert "!" not in query.tsquery
    assert "<->" not in query.tsquery
    assert build_keyword_query("???").tsquery == ""


def test_course_threshold_numbers_are_not_mistaken_for_document_identifiers() -> None:
    query = build_keyword_query("Lớp tối thiểu 70 sinh viên và tối đa 12 tín chỉ")

    assert query.document_codes == ()
    assert build_keyword_query("Quy định 956 PET01").document_codes == ("956",)
