from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture(scope="session")
def table():
    from raaga.theory.ragas import load_raga_table

    return load_raga_table(DATA / "ragas.json")
