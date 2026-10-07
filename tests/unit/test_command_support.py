from anu_unicode.command_support import page_range


def test_a_page_range_is_one_page_a_span_or_a_comma_list_of_both() -> None:
    assert page_range("51") == [51]
    assert page_range("4-6") == [4, 5, 6]
    assert page_range("11,51,67-68") == [11, 51, 67, 68]
    assert page_range("4-6,5,2") == [2, 4, 5, 6]
