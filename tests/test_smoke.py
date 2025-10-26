from samurai_sudoku.generator import generate_samurai
import random

def test_generate_unique():
    rng = random.Random(123)
    puzzle, solution = generate_samurai(rng, "easy")
    assert puzzle and solution