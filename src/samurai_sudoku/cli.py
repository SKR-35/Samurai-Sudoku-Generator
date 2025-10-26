from __future__ import annotations
import argparse
import concurrent.futures as cf
import os
import random
import sys
import time
from typing import List, Tuple

from reportlab.pdfgen.canvas import Canvas
from .generator import generate_samurai
from .pdf import PageSizeMap, draw_puzzle_page, draw_solutions_pages


def _count_clues(grid) -> int:
    return sum(1 for row in grid for v in row if v is not None)


# ---- worker (must be top-level for Windows pickling)
def _worker_task(args: Tuple[str, int, float, bool]) -> Tuple[str, int, object, object, float]:
    """
    Generate one puzzle/solution pair.
    Returns (difficulty, seed, puzzle, solution and seconds).
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


def main() -> None:
    p = argparse.ArgumentParser(description="Generate Samurai Sudoku PDF.")
    p.add_argument("--pages", type=int, default=1, help="Number of puzzles/pages (default: 1).")
    p.add_argument(
        "--difficulty",
        type=str,
        default="medium",
        choices=["easy", "medium", "hard", "evil"],
        help="Single difficulty for all pages (ignored if any per-level counts are given).",
    )
    # per-difficulty mix
    p.add_argument("--easy", type=int, default=None, help="How many EASY pages.")
    p.add_argument("--medium", type=int, default=None, help="How many MEDIUM pages.")
    p.add_argument("--hard", type=int, default=None, help="How many HARD pages.")
    p.add_argument("--evil", type=int, default=None, help="How many EVIL pages.")

    # io & runtime
    p.add_argument("--outfile", type=str, default="samurai_puzzles.pdf", help="Output PDF path.")
    p.add_argument("--pagesize", type=str, default="A4", choices=list(PageSizeMap.keys()), help="Page size.")
    p.add_argument("--seed", type=int, default=None, help="Master RNG seed for reproducibility.")
    p.add_argument("--workers", type=int, default=None, help="Number of parallel processes (default: CPU count).")
    p.add_argument("--uniq-timeout", type=float, default=10.0, help="Seconds allowed per uniqueness attempt.")
    p.add_argument("--no-adapt", action="store_true", help="Disable clue relaxation on timeouts.")
    p.add_argument("--quiet", action="store_true", help="Silence progress prints.")
    args = p.parse_args()

    # Build schedule
    any_mix = any(v is not None for v in (args.easy, args.medium, args.hard, args.evil))
    if any_mix:
        e = max(0, args.easy or 0)
        m = max(0, args.medium or 0)
        h = max(0, args.hard or 0)
        v = max(0, args.evil or 0)
        schedule: List[str] = (["easy"] * e) + (["medium"] * m) + (["hard"] * h) + (["evil"] * v)
        total_pages = len(schedule)
        if not args.quiet and args.pages != total_pages:
            print(f"Using per-difficulty totals ({total_pages}) instead of --pages={args.pages}.")
        args.pages = total_pages
    else:
        schedule = [args.difficulty] * args.pages

    pagesize = PageSizeMap[args.pagesize.upper()]

    # Handle zero pages
    if args.pages <= 0 or len(schedule) == 0:
        if not args.quiet:
            print("No puzzles requested (0 pages). Writing an empty PDF shell.")
        Canvas(args.outfile, pagesize=pagesize).save()
        if not args.quiet:
            print(f"Wrote {args.outfile} (empty).")
        return

    # Derive child seeds deterministically from master seed
    master = random.Random(args.seed)
    child_seeds = [master.randrange(2**63 - 1) for _ in range(len(schedule))]

    # Package worker items (this is where uniq_timeout/adapt are added)
    uniq_timeout = args.uniq_timeout
    adapt = not args.no_adapt
    work_items = [(d, s, uniq_timeout, adapt) for d, s in zip(schedule, child_seeds)]

    if not args.quiet:
        mix_str = ", ".join(f"{d}:{schedule.count(d)}" for d in ("easy", "medium", "hard", "evil") if d in schedule)
        print(
            f"Generating {len(schedule)} Samurai puzzle(s) "
            f"[{mix_str}] — pagesize={args.pagesize}, workers={args.workers or os.cpu_count()}"
        )
        sys.stdout.flush()

    # ---- Parallel generation
    t_all = time.time()
    results_ordered: List[Tuple[str, int, object, object, float]] = []
    with cf.ProcessPoolExecutor(max_workers=args.workers) as ex:
        # map preserves input order, so pages render in the intended sequence
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

    # ---- Render PDF (single process)
    c = Canvas(args.outfile, pagesize=pagesize)
    for i, (diff, seed, puzzle, solution, dt) in enumerate(results_ordered, start=1):
        draw_puzzle_page(c, puzzle, i, len(schedule), diff, pagesize)
        c.showPage()
    draw_solutions_pages(c, [sol for _, _, _, sol, _ in results_ordered], pagesize=pagesize, puzzles_per_row=2)
    c.save()

    if not args.quiet:
        print(
            f"Wrote {args.outfile} with {len(schedule)} puzzle page(s) + solutions "
            f"in {(time.time() - t_all) / 60:.1f} min."
        )


if __name__ == "__main__":
    main()