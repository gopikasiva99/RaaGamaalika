from raaga.theory.swaras import TOKEN_POSITION, positions


def test_shared_positions():
    assert TOKEN_POSITION["R2"] == TOKEN_POSITION["G1"] == 2
    assert TOKEN_POSITION["R3"] == TOKEN_POSITION["G2"] == 3
    assert TOKEN_POSITION["D2"] == TOKEN_POSITION["N1"] == 9
    assert TOKEN_POSITION["D3"] == TOKEN_POSITION["N2"] == 10


def test_positions_of_mohanam():
    assert positions(["S", "R2", "G3", "P", "D2", "S"]) == frozenset({0, 2, 4, 7, 9})
