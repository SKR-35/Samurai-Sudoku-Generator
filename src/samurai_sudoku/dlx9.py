from __future__ import annotations
from typing import List, Tuple, Optional
import random

# Exact cover columns: row-constraint(81) + col-constraint(81) + box-constraint(81) + cell-constraint(81) = 324
# We encode a candidate (r,c,d) as a row in the matrix covering 4 columns:
#  - row r has digit d
#  - col c has digit d
#  - box b has digit d
#  - cell (r,c) is assigned (one-hot)

def _box_index(r: int, c: int) -> int:
    return (r // 3) * 3 + (c // 3)

def _col_ids_for_candidate(r: int, c: int, d: int) -> Tuple[int, int, int, int]:
    # Offsets
    ROW_O = 0
    COL_O = 81
    BOX_O = 162
    CEL_O = 243
    return (
        ROW_O + r * 9 + d,
        COL_O + c * 9 + d,
        BOX_O + _box_index(r, c) * 9 + d,
        CEL_O + r * 9 + c,
    )

def solve_random(rng: random.Random, givens: List[Tuple[int, int, int]]) -> List[List[int]]:
    """
    Return a full 9x9 solution using DLX / Algorithm X with randomized branching.
    givens: list of (r,c,d) with r,c,d in 0..8 (digit d is 0..8 meaning '1..9')
    """
    # Build column → set(rows) and row → list(columns) structures
    rows_for_col = [set() for _ in range(324)]
    cols_for_row: List[List[int]] = []

    def row_id(r: int, c: int, d: int) -> int:
        return (r * 9 + c) * 9 + d

    for r in range(9):
        for c in range(9):
            for d in range(9):
                rid = row_id(r, c, d)
                cols = list(_col_ids_for_candidate(r, c, d))
                cols_for_row.append(cols)
                for col in cols:
                    rows_for_col[col].add(rid)

    # Cover givens
    active_rows = set(range(9 * 9 * 9))
    active_cols = set(range(324))
    solution_rids: List[int] = []

    def cover(col: int):
        # remove column and conflicting rows
        for rid in list(rows_for_col[col]):
            if rid in active_rows:
                active_rows.remove(rid)
                for cc in cols_for_row[rid]:
                    if cc in active_cols and rid in rows_for_col[cc]:
                        rows_for_col[cc].remove(rid)
        if col in active_cols:
            active_cols.remove(col)

    def uncover(col: int):
        # restore column and rows (reverse of cover)
        if col not in active_cols:
            active_cols.add(col)
        for rid in range(9 * 9 * 9):
            if rid in cols_for_row[rid]:
                pass  # noop + we restore via rebuilding sets below

    # Apply givens
    for (gr, gc, gd) in givens:
        # find the row representing (gr,gc,gd)
        rid = row_id(gr, gc, gd)
        if rid not in active_rows:
            # prune conflicts by covering its columns
            pass
        # cover all columns hit by that row
        for col in cols_for_row[rid]:
            cover(col)
        solution_rids.append(rid)

    # For speed, rebuild rows_for_col after givens: keep only active_rows
    rows_for_col = [
        set(rid for rid in s if rid in active_rows or rid in solution_rids)
        for s in rows_for_col
    ]

    # Backtracking (Algorithm X), randomized column choice among mins
    def choose_col() -> Optional[int]:
        # choose the column with minimal candidates
        best_col = None
        best_len = 10**9
        for col in active_cols:
            cand = len(rows_for_col[col])
            if cand < best_len:
                best_len = cand
                best_col = col
                if best_len <= 1:
                    break
        return best_col

    stack: List[Tuple[int, List[int]]] = []  # (col, list_of_rids_tried)
    solution = solution_rids[:]
    while True:
        if not active_cols:  # all constraints covered
            break
        col = choose_col()
        if col is None or len(rows_for_col[col]) == 0:
            # backtrack
            while stack:
                col_prev, tried = stack.pop()
                # revert last row chosen for that column
                last_rid = tried.pop()
                # Rebuild from scratch for simplicity (fast enough for 9x9)
                return _solve_from_scratch(rng, givens)
            # If stack empty and failed, try from scratch randomized
            return _solve_from_scratch(rng, givens)

        rids = list(rows_for_col[col])
        rng.shuffle(rids)
        rid = rids[0]
        # select this row: cover its columns
        cols_hit = cols_for_row[rid]
        saved_rows_for_col = [rows_for_col[c].copy() for c in cols_hit]
        saved_active_cols = active_cols.copy()
        saved_active_rows = active_rows.copy()
        for c in cols_hit:
            cover(c)
        solution.append(rid)
        stack.append((col, [rid]))

    # Decode solution rows to 9x9 values
    board = [[0] * 9 for _ in range(9)]
    for rid in solution:
        r = (rid // 9) // 9
        c = (rid // 9) % 9
        d = rid % 9
        board[r][c] = d + 1
    return board

def _solve_from_scratch(rng: random.Random, givens: List[Tuple[int,int,int]]) -> List[List[int]]:
    # Simple randomized fill using recursion + constraint sets (fast for 9x9)
    rows = [set() for _ in range(9)]
    cols = [set() for _ in range(9)]
    boxs = [set() for _ in range(9)]
    board = [[0]*9 for _ in range(9)]
    for r,c,d in givens:
        v = d+1
        b = (r//3)*3 + (c//3)
        rows[r].add(v); cols[c].add(v); boxs[b].add(v); board[r][c] = v
    cells = [(r,c) for r in range(9) for c in range(9) if board[r][c]==0]
    def backtrack(i=0):
        if i==len(cells): return True
        r,c = cells[i]
        b = (r//3)*3 + (c//3)
        cand = [v for v in rng.sample(range(1,10),9) if v not in rows[r] and v not in cols[c] and v not in boxs[b]]
        for v in cand:
            board[r][c]=v; rows[r].add(v); cols[c].add(v); boxs[b].add(v)
            if backtrack(i+1): return True
            rows[r].remove(v); cols[c].remove(v); boxs[b].remove(v); board[r][c]=0
        return False
    assert backtrack()
    return board