from __future__ import annotations
import random
from typing import List, Optional, Tuple
from .geometry import active_cells
from .model import Grid, candidates, is_cell_empty, is_valid_assignment

def find_next_cell(g: Grid) -> Optional[Tuple[int, int, List[int]]]:
    """MRV heuristic: choose empty cell with fewest candidates."""
    best: Optional[Tuple[int, int, List[int]]] = None
    for r, c in active_cells():
        if g[r][c] is None:
            cand = candidates(g, r, c)
            if not cand:
                return None
            if best is None or len(cand) < len(best[2]):
                best = (r, c, cand)
                if len(cand) == 1:
                    break
    return best

def solve_unique(g: Grid, limit_solutions: int = 2) -> Tuple[bool, int]:
    """
    Solve with backtracking, counting number of solutions up to limit_solutions.
    Returns (has_solution, count<=limit).
    """
    count = 0
    grid = g

    def backtrack() -> bool:
        nonlocal count
        nxt = find_next_cell(grid)
        if nxt is None:
            # Either no moves (dead) or already full. Check if full:
            # If no empty cells exist, solved.
            for r, c in active_cells():
                if grid[r][c] is None:
                    return False
            count += 1
            return count >= limit_solutions  # stop if enough
        r, c, cand = nxt
        random.shuffle(cand)
        for v in cand:
            if is_valid_assignment(grid, r, c, v):
                grid[r][c] = v
                if backtrack():
                    return True
                grid[r][c] = None
        return False

    backtrack()
    return (count > 0, count)