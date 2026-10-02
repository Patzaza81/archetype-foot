from journal.journal_sequences import sequence, analyser_sequences


def test_sequence_empty_rows_is_safe():
    result = sequence([])
    assert result["sequence"] == []
    assert result["longueur"] == 0
    assert result["issue_dernier"] is None
    assert result["serie_actuelle"] == 0
    assert result["type_serie"] is None


def test_analyser_sequences_empty_rows_is_safe():
    result = analyser_sequences([])
    assert result["sequence"] == []
    assert result["issue_dernier"] is None
    assert result["rupture"] is False
