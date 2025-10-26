from __future__ import annotations
import random, time
from typing import Tuple, List
from .geometry import active_cells, BOARDS, in_board
from .model import Grid, empty_samurai_grid
from .solver import solve_unique
from .dlx9 import solve_random

DIFFICULTY_CLUES = {
    "easy":   170,
    "medium": 140,
    "hard":   110,
    "evil":   80,
}

def _embed(board9: List[List[int]], g: Grid, r0: int, c0: int) -> None:
    for r in range(9):
        for c in range(9):
            g[r0 + r][c0 + c] = board9[r][c]

def _extract_overlap_givens(center9: List[List[int]], corner: str) -> List[tuple]:
    """Return givens (r,c,d0..8) for the overlapping 3x3 that corner shares with center."""
    # Overlaps are:
    # TL ↔ center at TL's bottom-right 3x3 == center's top-left 3x3
    # TR ↔ center at TR's bottom-left 3x3 == center's top-right 3x3
    # BL ↔ center at BL's top-right 3x3 == center's bottom-left 3x3
    # BR ↔ center at BR's top-left 3x3 == center's bottom-right 3x3
    m = {
        "TL": ((6,6), (0,0)),
        "TR": ((6,12),(0,6)),
        "BL": ((12,6),(6,0)),
        "BR": ((12,12),(6,6)),
    }
    (cr0, cc0), (sr0, sc0) = m[corner]  # corner origin in global, and subgrid origin inside center
    givens = []
    # map the 3x3 inside the corner's 9x9 where it overlaps:
    # inside the corner board, the overlapping block is at:
    pos = {
        "TL": (6,6),
        "TR": (6,0),
        "BL": (0,6),
        "BR": (0,0),
    }[corner]
    pr0, pc0 = pos
    for dr in range(3):
        for dc in range(3):
            v = center9[sr0 + dr][sc0 + dc]
            # givens for corner DLX are 0-based digits
            givens.append((pr0 + dr, pc0 + dc, v - 1))
    return givens

def _solve_samurai_by_composition(rng: random.Random) -> Grid:
    """Fast: solve center with DLX, then each corner constrained by its overlap 3x3."""
    g = empty_samurai_grid()
    # 1) center
    center9 = solve_random(rng, givens=[])
    # 2) corners with overlap givens from center
    tl = solve_random(rng, _extract_overlap_givens(center9, "TL"))
    tr = solve_random(rng, _extract_overlap_givens(center9, "TR"))
    bl = solve_random(rng, _extract_overlap_givens(center9, "BL"))
    br = solve_random(rng, _extract_overlap_givens(center9, "BR"))
    # 3) stitch
    _embed(tl, g, 0, 0)
    _embed(tr, g, 0, 12)
    _embed(center9, g, 6, 6)
    _embed(bl, g, 12, 0)
    _embed(br, g, 12, 12)
    return g

def _dig_holes_to_target(rng: random.Random, solved: Grid, target_clues: int,
                         uniq_timeout_s: float = 10.0) -> Grid:
    """Greedy dig with uniqueness checks, with a per-check timeout; adapt clues if needed."""
    puzzle = [row[:] for row in solved]
    actives = [(r, c) for (r, c) in active_cells()]
    rng.shuffle(actives)

    def count_clues(g: Grid) -> int:
        return sum(1 for (r, c) in actives if g[r][c] is not None)

    for r, c in actives:
        if count_clues(puzzle) <= target_clues:
            break
        v = puzzle[r][c]
        if v is None:
            continue
        puzzle[r][c] = None
        # time-boxed uniqueness
        start = time.time()
        has, nsol = solve_unique([row[:] for row in puzzle], limit_solutions=2)
        if (time.time() - start) > uniq_timeout_s or (not has or nsol != 1):
            puzzle[r][c] = v  # restore if timed out or non-unique
    return puzzle

def generate_samurai(rng: random.Random, difficulty: str,
                     uniq_timeout_s: float = 10.0, adapt: bool = True) -> Tuple[Grid, Grid]:
    """Return (puzzle, solution) using the fast composed method + adaptive dig."""
    difficulty = difficulty.lower()
    if difficulty not in DIFFICULTY_CLUES:
        raise ValueError(f"Unknown difficulty: {difficulty}")
    base_target = DIFFICULTY_CLUES[difficulty]

    # FAST solved Samurai
    solved = _solve_samurai_by_composition(rng)

    # Dig with time-boxed uniqueness + adapt target slightly if needed
    target = base_target
    for attempt in range(3):
        puzzle = _dig_holes_to_target(rng, solved, target_clues=target, uniq_timeout_s=uniq_timeout_s)
        has, nsol = solve_unique([row[:] for row in puzzle], limit_solutions=2)
        if has and nsol == 1:
            return puzzle, solved
        if not adapt:
            break
        # too hard to certify, then relax a bit (more clues)
        target += 10
    # Fallback: return a more clued puzzle to guarantee uniqueness quickly
    puzzle = _dig_holes_to_target(rng, solved, target_clues=max(base_target, 210), uniq_timeout_s=uniq_timeout_s)
    return puzzle, solved