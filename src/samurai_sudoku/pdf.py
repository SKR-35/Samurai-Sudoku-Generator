from __future__ import annotations
from typing import List, Tuple

from reportlab.lib.pagesizes import A4, LETTER, LEGAL
from reportlab.lib.units import mm, inch
from reportlab.pdfgen.canvas import Canvas

from .geometry import BOARDS, in_board

# Built-ins plus two handy trim sizes for puzzle books
PageSizeMap = {
    "A4": A4,
    "LETTER": LETTER,
    "LEGAL": LEGAL,
    "6X9": (6 * inch, 9 * inch),
    "8X10": (8 * inch, 10 * inch)
}

# -------------------------------
# Grid drawing helpers (scaled)
# -------------------------------

def _line_widths_for_cell(cell: float, mini: bool) -> tuple[float, float]:
    """
    Return (thin, thick) line widths scaled to the cell size.
    Miniatures get lighter strokes.
    """
    if mini:
        thin = max(0.25, cell * 0.035)
        thick = max(0.8,  cell * 0.12)
    else:
        thin = max(0.4,  cell * 0.05)
        thick = max(1.6, cell * 0.16)
    return thin, thick


def _draw_board_lines(c: Canvas, x0: float, y0: float, cell: float, *, mini: bool) -> None:
    thin, thick = _line_widths_for_cell(cell, mini)
    # thin grid
    c.setLineWidth(thin)
    for i in range(10):
        c.line(x0 + i * cell, y0, x0 + i * cell, y0 + 9 * cell)   # vertical
        c.line(x0, y0 + i * cell, x0 + 9 * cell, y0 + i * cell)   # horizontal
    # thick subgrid borders
    c.setLineWidth(thick)
    for i in range(0, 10, 3):
        c.line(x0 + i * cell, y0, x0 + i * cell, y0 + 9 * cell)
        c.line(x0, y0 + i * cell, x0 + 9 * cell, y0 + i * cell)


def _cell_positions_samurai(x_origin: float, y_origin: float, cell: float) -> dict:
    """
    Board anchors relative to the Samurai origin.
    """
    return {
        "TL": (x_origin + 0 * cell,  y_origin + 12 * cell),
        "TR": (x_origin + 12 * cell, y_origin + 12 * cell),
        "C":  (x_origin + 6 * cell,  y_origin + 6 * cell),
        "BL": (x_origin + 0 * cell,  y_origin + 0 * cell),
        "BR": (x_origin + 12 * cell, y_origin + 0 * cell),
    }


def _draw_samurai_outline(c: Canvas, x_origin: float, y_origin: float, cell: float, *, mini: bool) -> None:
    pos = _cell_positions_samurai(x_origin, y_origin, cell)
    for name in ["TL", "TR", "C", "BL", "BR"]:
        x0, y0 = pos[name]
        _draw_board_lines(c, x0, y0, cell, mini=mini)


def _font_size_for_cell(cell: float, mini: bool) -> float:
    """
    A readable font-size that fits comfortably in the cell.
    """
    if mini:
        fs = cell * 0.52   # a touch smaller in miniatures
        return max(5.0, min(11.0, fs))
    else:
        fs = cell * 0.60
        return max(8.0, min(16.0, fs))


def _draw_digits(c: Canvas, grid, x_origin: float, y_origin: float, cell: float, *, mini: bool) -> None:
    """
    Draw numbers centered inside any active 21×21 cell.
    Uses font-size derived from the cell size to avoid overflow.
    """
    fs = _font_size_for_cell(cell, mini)
    c.setFont("Helvetica", fs)

    for r in range(21):
        for cc in range(21):
            # skip inactive cells
            if not any(in_board(r, cc, r0, c0) for _, r0, c0 in BOARDS):
                continue
            v = grid[r][cc]
            if v is None:
                continue
            x_center = x_origin + cc * cell + cell * 0.5
            # baseline slightly below center improves optical centering
            y_base = y_origin + r * cell + (cell * 0.5 - fs * 0.30)
            c.drawCentredString(x_center, y_base, str(v))

# -------------------------------
# Page-level helpers
# -------------------------------

def _difficulty_to_stars_label(diff: str) -> Tuple[str, str]:
    m = {
        "easy":   ("★", "Easy"),
        "medium": ("★★", "Medium"),
        "hard":   ("★★★", "Hard"),
        "evil":   ("★★★★", "Evil"),
    }
    return m[diff]


def draw_puzzle_page(canvas: Canvas, puzzle, page_num: int, total_pages: int, diff: str, pagesize) -> None:
    W, H = pagesize
    margin = 15 * mm

    # Header
    canvas.setFont("Helvetica-Bold", 16)
    canvas.drawString(margin, H - margin, f"Samurai Sudoku — Puzzle {page_num}/{total_pages}")
    stars, label = _difficulty_to_stars_label(diff)
    canvas.setFont("Helvetica", 12)
    canvas.drawString(margin, H - margin - 16, f"Difficulty: {label} {stars}")

    # Layout
    usable_w = W - 2 * margin
    usable_h = H - 3 * margin - 20
    cell = min(usable_w / 21.0, usable_h / 21.0)
    x_origin = (W - 21 * cell) / 2.0
    y_origin = margin

    _draw_samurai_outline(canvas, x_origin, y_origin, cell, mini=False)
    _draw_digits(canvas, puzzle, x_origin, y_origin, cell, mini=False)
    
    canvas.setFont("Helvetica-Oblique", 9)
    canvas.drawRightString(W - margin, margin * 0.7, f"Page {page_num}/{total_pages}")

def draw_solutions_pages(canvas: Canvas, solutions: List, pagesize, puzzles_per_row: int = 2) -> None:
    """
    Append compact solution thumbnails. Digits and line widths scale to cell size.
    """
    W, H = pagesize
    margin = 15 * mm

    canvas.showPage()
    canvas.setFont("Helvetica-Bold", 16)
    canvas.drawString(margin, H - margin, "Solutions")

    cols = puzzles_per_row
    rows = max(1, (len(solutions) + cols - 1) // cols)

    top_area = H - margin - 20
    grid_h = top_area - margin
    grid_w = W - 2 * margin

    mw = grid_w / cols
    mh = grid_h / rows

    # Miniature cell size per Samurai (21x21)
    cell = min((mw - 10) / 21.0, (mh - 10) / 21.0)

    idx = 0
    for r in range(rows):
        for c in range(cols):
            if idx >= len(solutions):
                break
            x_origin = margin + c * mw + (mw - (21 * cell)) / 2.0
            y_origin = margin + (rows - 1 - r) * mh + (mh - (21 * cell)) / 2.0

            _draw_samurai_outline(canvas, x_origin, y_origin, cell, mini=True)
            _draw_digits(canvas, solutions[idx], x_origin, y_origin, cell, mini=True)

            canvas.setFont("Helvetica", 8)
            canvas.drawString(x_origin, y_origin + 21 * cell + 4, f"#{idx + 1}")
            idx += 1