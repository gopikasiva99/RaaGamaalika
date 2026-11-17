import json

import pytest

from conftest import DATA
from raaga.theory.ragas import load_raga_table, normalize_name


def test_table_size_and_validity(table):
    assert len(table.ragas) >= 300
    assert sum(r.melakarta is not None for r in table.ragas.values()) == 72


def test_known_scales(table):
    assert table.resolve("Mohanam").aro_positions == {0, 2, 4, 7, 9}
    assert table.resolve("Bilahari").aro_positions == {0, 2, 4, 7, 9}
    assert table.resolve("Bilahari").avaro_positions == {0, 2, 4, 5, 7, 9, 11}
    assert table.resolve("Hamsadhwani").allowed == {0, 2, 4, 7, 11}
    assert table.resolve("Hindolam").allowed == {0, 3, 5, 8, 10}
    for name in ["Kalyani", "Thodi", "Bhairavi", "Kambhoji", "Sahana", "Darbar",
                 "Nayaki", "Kanada", "Begada", "Madhyamavati", "Saveri", "Atana",
                 "Shankarabharanam", "Mayamalavagowla", "Keeravani", "Shanmukhapriya",
                 "Pantuvarali", "Kharaharapriya", "Harikambhoji", "Abhogi", "Sri"]:
        assert table.resolve(name) is not None, name


def test_performance_names_point_at_melakartas(table):
    assert table.resolve("Thodi").melakarta == 8
    assert table.resolve("Shankarabharanam").melakarta == 29
    assert table.resolve("Kalyani").melakarta == 65
    assert table.resolve("Pantuvarali").melakarta == 51


def test_aliases_unique():
    entries = json.loads((DATA / "ragas.json").read_text(encoding="utf-8"))
    owner = {}
    for e in entries:
        for a in [e["name"], e["id"], *e["aliases"]]:
            k = normalize_name(a)
            assert owner.setdefault(k, e["id"]) == e["id"], f"{a!r} -> {owner[k]} and {e['id']}"


def test_validation_rejects_bad_token(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text(json.dumps([{"name": "X", "parent": 29, "melakarta": None,
                              "arohana": ["S", "Q9", "S"], "avarohana": ["S"]}]))
    with pytest.raises(ValueError, match="X"):
        load_raga_table(p)


def test_validation_rejects_wrong_melakarta_scale(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text(json.dumps([{"name": "Fake", "parent": 29, "melakarta": 29,
                              "arohana": ["S", "R1", "G3", "M1", "P", "D2", "N3", "S"],
                              "avarohana": ["S", "N3", "D2", "P", "M1", "G3", "R1", "S"]}]))
    with pytest.raises(ValueError, match="Fake"):
        load_raga_table(p)


def test_validation_rejects_foreign_swara_unless_bhashanga(tmp_path):
    base = {"name": "Y", "parent": 29, "melakarta": None,
            "arohana": ["S", "R2", "G3", "M2", "P", "S"], "avarohana": ["S", "P", "M2", "G3", "R2", "S"]}
    p = tmp_path / "bad.json"
    p.write_text(json.dumps([base]))
    with pytest.raises(ValueError, match="Y"):
        load_raga_table(p)
    p.write_text(json.dumps([{**base, "bhashanga": True}]))
    assert load_raga_table(p).resolve("Y") is not None
