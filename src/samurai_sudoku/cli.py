# src/samurai_sudoku/cli.py
from __future__ import annotations
import argparse
import concurrent.futures as cf
import os
import random
import sqlite3
import sys
import time
from typing import List, Tuple, Optional

from reportlab.pdfgen.canvas import Canvas

from .generator import generate_samurai
from .pdf import PageSizeMap, draw_puzzle_page, draw_solutions_pages
from .db import open_db, ensure_schema, insert_run, insert_puzzle

# ------------------------------------
# Utilities
# ------------------------------------

def _count_clues(grid) -> int:
    return sum(1 for row in grid for v in row if v is not None)

def _decode_grid(txt: str) -> List[List[Optional[int]]]:
    """Inverse of db.grid_to_text: 441-char string -> 21x21 grid with ints/None."""
    assert len(txt) == 21 * 21
    g: List[List[Optional[int]]] = [[None] * 21 for _ in range(21)]
    k = 0
    for r in range(21):
        for c in range(21):
            ch = txt[k]; k += 1
            if ch.isdigit() and ch != "0":
                g[r][c] = int(ch)
            else:
                g[r][c] = None
    return g

# ------------------------------------
# Worker (must be top-level for Windows pickling)
# ------------------------------------

def _worker_task(args: Tuple[str, int, float, bool]) -> Tuple[str, int, object, object, float]:
    """
    Generate one puzzle/solution pair.
    Returns (difficulty, seed, puzzle, solution, seconds).
    """
    difficulty, seed, uniq_timeout, adapt = args
    rng = random.Random(seed)
    t0 = time.time()
    puzzle, solution = generate_samurai(
        rng,
        difficulty,
        uniq_timeout_s=uniq_timeout,
        adapt=adapt,
    )
    return (difficulty, seed, puzzle, solution, time.time() - t0)

# ------------------------------------
# Main
# ------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(description="Generate Samurai Sudoku PDFs and/or store runs to SQLite.")
    # generation controls
    p.add_argument("--pages", type=int, default=1, help="Number of puzzles/pages (default: 1).")
    p.add_argument(
        "--difficulty",
        type=str,
        default="medium",
        choices=["easy", "medium", "hard", "evil"],
        help="Single difficulty for all pages (ignored if any per-level counts are given).",
    )
    p.add_argument("--easy", type=int, default=None, help="How many EASY pages.")
    p.add_argument("--medium", type=int, default=None, help="How many MEDIUM pages.")
    p.add_argument("--hard", type=int, default=None, help="How many HARD pages.")
    p.add_argument("--evil", type=int, default=None, help="How many EVIL pages.")
    p.add_argument("--seed", type=int, default=None, help="Master RNG seed for reproducibility.")
    p.add_argument("--workers", type=int, default=None, help="Number of parallel processes (default: CPU count).")
    p.add_argument("--uniq-timeout", type=float, default=10.0, help="Seconds allowed per uniqueness attempt.")
    p.add_argument("--no-adapt", action="store_true", help="Disable clue relaxation on timeouts.")
    p.add_argument("--quiet", action="store_true", help="Silence progress prints.")

    # outputs
    p.add_argument("--outfile", type=str, default="samurai_puzzles.pdf", help="Output PDF path.")
    p.add_argument("--pagesize", type=str, default="A4", choices=list(PageSizeMap.keys()), help="Page size.")
    p.add_argument("--db", type=str, default=None, help="Write results to this SQLite file (e.g., puzzles.db).")
    p.add_argument("--no-pdf", action="store_true", help="Do not write PDF (useful with --db).")

    # DB -> PDF export mode
    p.add_argument(
        "--export-ids",
        type=str,
        default=None,
        help="Comma-separated puzzle IDs to export from --db to PDF (skips generation). Example: 5,9,12",
    )

    args = p.parse_args()

    # Resolve page size
    pagesize = PageSizeMap[args.pagesize.upper()]

    # ------------------------------
    # EXPORT MODE: --export-ids + --db
    # ------------------------------
    if args.export_ids:
        if not args.db:
            p.error("--export-ids requires --db (SQLite path).")
        id_list = [int(x.strip()) for x in args.export_ids.split(",") if x.strip()]
        if len(id_list) == 0:
            p.error("No valid IDs provided to --export-ids.")
        if args.no_pdf:
            p.error("--export-ids cannot be used with --no-pdf (export writes a PDF).")

        # Fetch puzzles in the given order
        conn = open_db(args.db)
        ensure_schema(conn)
        q_marks = ",".join("?" for _ in id_list)
        rows = conn.execute(
            f"""SELECT id, difficulty, seed, clues, seconds, puzzle_txt, solution_txt
                FROM puzzles
                WHERE id IN ({q_marks})""",
            id_list,
        ).fetchall()
        # Put back in requested order
        row_by_id = {r[0]: r for r in rows}
        ordered = []
        missing = []
        for pid in id_list:
            if pid in row_by_id:
                ordered.append(row_by_id[pid])
            else:
                missing.append(pid)
        if missing and not args.quiet:
            print(f"⚠ Skipped missing puzzle IDs (not in DB): {missing}")

        if not ordered:
            if not args.quiet:
                print("No puzzles found to export. Nothing written.")
            return

        # Decode and render
        c = Canvas(args.outfile, pagesize=pagesize)
        puzzles = []
        solutions = []
        for i, (_pid, diff, seed, clues, seconds, ptxt, stxt) in enumerate(ordered, start=1):
            puzzle = _decode_grid(ptxt)
            solution = _decode_grid(stxt)
            puzzles.append((diff, seed, puzzle, solution, float(seconds)))

        for i, (diff, seed, puzzle, solution, dt) in enumerate(puzzles, start=1):
            draw_puzzle_page(c, puzzle, i, len(puzzles), diff, pagesize)
            c.showPage()
        draw_solutions_pages(c, [sol for _, _, _, sol, _ in puzzles], pagesize=pagesize, puzzles_per_row=2)
        c.save()

        if not args.quiet:
            print(f"✔ Exported {len(puzzles)} puzzle(s) from DB → {args.outfile}")
        return

    # ------------------------------
    # GENERATION MODE
    # ------------------------------

    # Build schedule (mixed difficulties override --pages)
    any_mix = any(v is not None for v in (args.easy, args.medium, args.hard, args.evil))
    if any_mix:
        e = max(0, args.easy or 0)
        m = max(0, args.medium or 0)
        h = max(0, args.hard or 0)
        v = max(0, args.evil or 0)
        schedule: List[str] = (["easy"] * e) + (["medium"] * m) + (["hard"] * h) + (["evil"] * v)
        total_pages = len(schedule)
        if not args.quiet and args.pages != total_pages:
            print(f"ℹ Using per-difficulty totals ({total_pages}) instead of --pages={args.pages}.")
        args.pages = total_pages
    else:
        schedule = [args.difficulty] * args.pages

    # Zero pages → optional empty PDF
    if args.pages <= 0 or len(schedule) == 0:
        if args.no_pdf:
            if not args.quiet:
                print("No puzzles requested and --no-pdf set. Done.")
            return
        if not args.quiet:
            print("No puzzles requested (0 pages). Writing an empty PDF shell.")
        Canvas(args.outfile, pagesize=pagesize).save()
        if not args.quiet:
            print(f"✔ Wrote {args.outfile} (empty).")
        return

    # Derive child seeds deterministically from master seed
    master = random.Random(args.seed)
    child_seeds = [master.randrange(2**63 - 1) for _ in range(len(schedule))]

    uniq_timeout = args.uniq_timeout
    adapt = not args.no_adapt
    work_items = [(d, s, uniq_timeout, adapt) for d, s in zip(schedule, child_seeds)]

    if not args.quiet:
        mix_str = ", ".join(f"{d}:{schedule.count(d)}" for d in ("easy", "medium", "hard", "evil") if d in schedule)
        print(
            f"▶ Generating {len(schedule)} Samurai puzzle(s) "
            f"[{mix_str}] — pagesize={args.pagesize}, workers={args.workers or os.cpu_count()}"
        )
        sys.stdout.flush()

    # Parallel generation
    t_all = time.time()
    results_ordered: List[Tuple[str, int, object, object, float]] = []
    with cf.ProcessPoolExecutor(max_workers=args.workers) as ex:
        for res in ex.map(_worker_task, work_items):
            results_ordered.append(res)
            if not args.quiet:
                idx = len(results_ordered)
                diff, seed, puzzle, solution, dt = res
                clues = _count_clues(puzzle)
                mean_t = sum(r[-1] for r in results_ordered) / idx
                eta = mean_t * (len(schedule) - idx)
                print(f"[{idx}/{len(schedule)}] ({diff}) done in {dt:.1f}s (clues={clues}) — ETA {eta/60:.1f} min")
                sys.stdout.flush()

    # Optional SQLite write
    if args.db:
        conn = open_db(args.db)
        ensure_schema(conn)
        run_id = insert_run(
            conn,
            args={
                "seed": args.seed,
                "pagesize": args.pagesize,
                "uniq_timeout": args.uniq_timeout,
                "no_adapt": args.no_adapt,
                "workers": args.workers,
                "easy": args.easy, "medium": args.medium, "hard": args.hard, "evil": args.evil,
                "pages": args.pages,
                "outfile": args.outfile,
            },
            schedule=[d for d, *_ in results_ordered],
        )
        for i, (diff, seed, puzzle, solution, seconds) in enumerate(results_ordered, start=1):
            clues = _count_clues(puzzle)
            insert_puzzle(
                conn,
                run_id=run_id,
                idx_in_run=i,
                difficulty=diff,
                seed=seed,
                clues=clues,
                seconds=seconds,
                puzzle=puzzle,
                solution=solution,
            )
        if not args.quiet:
            print(f"✔ Saved {len(results_ordered)} puzzle(s) to SQLite: {args.db} (run_id={run_id})")

    # PDF output (unless suppressed)
    if not args.no_pdf:
        c = Canvas(args.outfile, pagesize=pagesize)
        for i, (diff, seed, puzzle, solution, dt) in enumerate(results_ordered, start=1):
            draw_puzzle_page(c, puzzle, i, len(results_ordered), diff, pagesize)
            c.showPage()
        draw_solutions_pages(c, [sol for _, _, _, sol, _ in results_ordered], pagesize=pagesize, puzzles_per_row=2)
        c.save()
        if not args.quiet:
            print(
                f"✔ Wrote {args.outfile} with {len(results_ordered)} puzzle page(s) + solutions "
                f"in {(time.time() - t_all) / 60:.1f} min."
            )
    else:
        if not args.quiet:
            print("✔ Generation complete (PDF suppressed with --no-pdf).")

if __name__ == "__main__":
    main()