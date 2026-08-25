from app.curriculum import LESSON_CONTENT, UNITS, find_lesson, public_card

def test_course_has_ten_units_and_depth():
    assert len(UNITS) == 10
    assert sum(len(unit[4]) for unit in UNITS) >= 70

def test_public_cards_never_leak_answers():
    for lesson in LESSON_CONTENT.values():
        for card in lesson["cards"]:
            public = public_card(card)
            assert "answer" not in public
            assert "tolerance" not in public

def test_authored_lessons_exist_on_path():
    for slug in LESSON_CONTENT:
        assert find_lesson(slug) is not None
