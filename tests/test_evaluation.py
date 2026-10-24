from scripts.evaluate import score_message


def test_wrong_category_does_not_hide_correct_fields():
    message = {'kind': 'confirmation', 'owner': 'Alex', 'text': 'Alex will confirm on 2026-10-26 at 09:00.'}
    item = {'kind': 'appointment', 'owner_id': 1, 'due_at': '2026-10-26T09:00:00+05:00', 'change_type': 'new'}
    score = score_message(message, [item])
    assert (score['tp'], score['fp'], score['fn']) == (0, 1, 1)
    assert score['owner_correct'] is True
    assert score['date_correct'] is True


def test_failed_prediction_keeps_field_denominators():
    message = {'kind': 'transport', 'owner': 'Alex', 'text': 'Alex will drive on 2026-10-26 at 09:00.'}
    score = score_message(message, [])
    assert score['owner_correct'] is False
    assert score['date_correct'] is False
    assert score['fn'] == 1


def test_multiple_predictions_do_not_mix_field_matches():
    message = {'kind': 'transport', 'owner': 'Alex', 'text': 'Alex will drive on 2026-10-26 at 09:00.'}
    items = [{'kind': 'transport', 'owner_id': 1, 'due_at': None},
             {'kind': 'transport', 'owner_id': None, 'due_at': '2026-10-26T09:00:00+05:00'}]
    score = score_message(message, items)
    assert (score['tp'], score['fp'], score['fn']) == (1, 1, 0)
    assert score['owner_correct'] is False
    assert score['date_correct'] is False
