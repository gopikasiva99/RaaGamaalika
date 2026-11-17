import pytest

from raaga.theory.ragas import Raga, RagaTable, melakarta_scale, normalize_name, slugify


@pytest.mark.parametrize("n,scale", [
    (8, ("S", "R1", "G2", "M1", "P", "D1", "N2")),    # Hanumatodi
    (15, ("S", "R1", "G3", "M1", "P", "D1", "N3")),   # Mayamalavagowla
    (22, ("S", "R2", "G2", "M1", "P", "D2", "N2")),   # Kharaharapriya
    (29, ("S", "R2", "G3", "M1", "P", "D2", "N3")),   # Dheerasankarabharanam
    (65, ("S", "R2", "G3", "M2", "P", "D2", "N3")),   # Mechakalyani
])
def test_melakarta_scale(n, scale):
    assert melakarta_scale(n) == scale


@pytest.mark.parametrize("a,b", [
    ("Thodi", "Todi"), ("Tōḍi", "Thodi"),
    ("Shankarabharanam", "Śankarābharaṇaṁ"), ("Sankarabharanam", "Shankarabharanam"),
    ("Mohanam", "mohanam "), ("Kalyaani", "Kalyani"),
])
def test_normalize_equivalent(a, b):
    assert normalize_name(a) == normalize_name(b)


def test_slugify_is_readable():
    assert slugify("Hamsadhwani") == "hamsadhwani"
    assert slugify("Śankarābharaṇaṁ") == "sankarabharanam"


def _raga(name, aro, avaro, parent, aliases=()):
    return Raga(id=slugify(name), name=name, aliases=tuple(aliases), melakarta=None,
                parent=parent, arohana=tuple(aro.split()), avarohana=tuple(avaro.split()),
                vakra=False, bhashanga=False)


@pytest.fixture
def tiny_table():
    return RagaTable([
        _raga("Mohanam", "S R2 G3 P D2 S", "S D2 P G3 R2 S", 28),
        _raga("Bilahari", "S R2 G3 P D2 S", "S N3 D2 P M1 G3 R2 S", 29),
        _raga("Hindolam", "S G2 M1 D1 N2 S", "S N2 D1 M1 G2 S", 20),
    ])


def test_raga_positions(tiny_table):
    b = tiny_table.get("bilahari")
    assert b.aro_positions == {0, 2, 4, 7, 9}
    assert b.avaro_positions == {0, 2, 4, 5, 7, 9, 11}
    assert b.allowed == {0, 2, 4, 5, 7, 9, 11}


def test_search_and_resolve(tiny_table):
    assert tiny_table.resolve("mohanam").id == "mohanam"
    assert tiny_table.resolve("Mohanam ").id == "mohanam"
    assert tiny_table.resolve("nothing") is None
    assert [r.id for r in tiny_table.search("bil")] == ["bilahari"]
