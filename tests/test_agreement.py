from tariff_trail.agreement import agreed_heading


def test_same_heading_different_codes():
    assert agreed_heading("3926305000", "3926901000", "3926100000") == "3926"


def test_full_agreement_is_also_heading_agreement():
    assert agreed_heading("9505906000", "9505906000", "9505906000") == "9505"


def test_split_heading_is_not_agreed():
    assert agreed_heading("3926305000", "8713100000", "3926305000") == ""


def test_missing_source_is_not_agreed():
    assert agreed_heading("3926305000", "3926305000", "") == ""
    assert agreed_heading("3926305000", None, "3926305000") == ""
    assert agreed_heading("", "", "") == ""


def test_short_code_is_not_agreed():
    assert agreed_heading("392", "392", "392") == ""
