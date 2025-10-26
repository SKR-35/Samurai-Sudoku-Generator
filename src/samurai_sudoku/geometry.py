from typing import Iterable, List, Tuple

# Global Samurai canvas is 21x21. Inactive cells are None.
BOARD_SIZE = 21

# Five 9x9 boards: Top-Left, Top-Right, Center, Bottom-Left, Bottom-Right
BOARDS = [
    ("TL", 0, 0),
    ("TR", 0, 12),
    ("C", 6, 6),
    ("BL", 12, 0),
    ("BR", 12, 12),
]

def in_board(r: int, c: int, r0: int, c0: int) -> bool:
    return r0 <= r < r0 + 9 and c0 <= c < c0 + 9

def is_active_cell(r: int, c: int) -> bool:
    return any(in_board(r, c, r0, c0) for _, r0, c0 in BOARDS)

def active_cells() -> List[Tuple[int, int]]:
    return [(r, c) for r in range(BOARD_SIZE) for c in range(BOARD_SIZE) if is_active_cell(r, c)]

def boards_covering_cell(r: int, c: int) -> List[Tuple[str, int, int]]:
    return [(name, r0, c0) for (name, r0, c0) in BOARDS if in_board(r, c, r0, c0)]

def row_cells_in_board(r0: int, c0: int, rr: int) -> Iterable[Tuple[int, int]]:
    for cc in range(9):
        yield r0 + rr, c0 + cc

def col_cells_in_board(r0: int, c0: int, cc: int) -> Iterable[Tuple[int, int]]:
    for rr in range(9):
        yield r0 + rr, c0 + cc

def box_cells_in_board(r0: int, c0: int, br: int, bc: int) -> Iterable[Tuple[int, int]]:
    for rr in range(br * 3, br * 3 + 3):
        for cc in range(bc * 3, bc * 3 + 3):
            yield r0 + rr, c0 + cc

def subgrid_index(r: int, c: int, r0: int, c0: int) -> Tuple[int, int]:
    rr = r - r0
    cc = c - c0
    return rr // 3, cc // 3