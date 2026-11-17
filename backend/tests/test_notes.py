import pytest

from raaga.notes import hz_to_note, note_to_hz_near


def test_notes():
    assert hz_to_note(138.6) == "C#"
    assert hz_to_note(146.83) == "D"
    assert abs(note_to_hz_near("D", 150) - 146.83) < 0.1
    assert abs(note_to_hz_near("D", 280) - 293.66) < 0.1


def test_bad_note():
    with pytest.raises(ValueError):
        note_to_hz_near("H#", 150)
