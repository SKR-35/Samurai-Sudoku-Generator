from __future__ import annotations
from typing import List, Optional, Tuple
from .geometry import BOARD_SIZE, is_active_cell, boards_covering_cell, subgrid_index

Value = Optional[int]  # 1..9 or None
Grid = List[List[Value]]  # 21x21 with None for inactive cells + also None for empty active

def empty_samurai_grid() -> Grid:
    g: Grid = [[None for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            if is_active_cell(r, c):
                g[r][c] = None
            else:
                g[r][c] = None  # keep None but treated as inactive by geometry
    return g

def copy_grid(g: Grid) -> Grid:
    return [row[:] for row in g]

def is_cell_empty(g: Grid, r: int, c: int) -> bool:
    return g[r][c] is None

def candidates(g: Grid, r: int, c: int) -> List[int]:
    """Return allowed digits 1..9 at (r,c) respecting ALL boards covering that cell."""
    used = set()
    for _, r0, c0 in boards_covering_cell(r, c):
        # row
        rr = r - r0
        for cc in range(9):
            v = g[r0 + rr][c0 + cc]
            if v is not None:
                used.add(v)
        # col
        cc = c - c0
        for rr2 in range(9):
            v = g[r0 + rr2][c0 + cc]
            if v is not None:
                used.add(v)
        # box
        br, bc = subgrid_index(r, c, r0, c0)
        for rr3 in range(br * 3, br * 3 + 3):
            for cc3 in range(bc * 3, bc * 3 + 3):
                v = g[r0 + rr3][c0 + cc3]
                if v is not None:
                    used.add(v)
    return [d for d in range(1, 10) if d not in used]

def is_valid_assignment(g: Grid, r: int, c: int, v: int) -> bool:
    """Fast validity check for placing v at (r,c)."""
    for _, r0, c0 in boards_covering_cell(r, c):
        rr = r - r0
        cc = c - c0
        # row
        for x in range(9):
            if (c0 + x) != c and g[r0 + rr][c0 + x] == v:
                return False
        # col
        for y in range(9):
            if (r0 + y) != r and g[r0 + y][c0 + cc] == v:
                return False
        # box
        br = (rr // 3) * 3
        bc = (cc // 3) * 3
        for y in range(3):
            for x in range(3):
                R, C = r0 + br + y, c0 + bc + x
                if (R, C) != (r, c) and g[R][C] == v:
                    return False
    return True