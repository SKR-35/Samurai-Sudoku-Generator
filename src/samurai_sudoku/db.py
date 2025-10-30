# src/samurai_sudoku/db.py
from __future__ import annotations
import json, sqlite3, time
from typing import Any, Dict, Iterable, List, Optional, Tuple

Grid = List[List[Optional[int]]]

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS runs (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  created_utc   INTEGER NOT NULL,
  seed          INTEGER,
  pages         INTEGER NOT NULL,
  pagesize      TEXT NOT NULL,
  uniq_timeout  REAL NOT NULL,
  adapt         INTEGER NOT NULL,
  workers       INTEGER,
  mix_easy      INTEGER NOT NULL,
  mix_medium    INTEGER NOT NULL,
  mix_hard      INTEGER NOT NULL,
  mix_evil      INTEGER NOT NULL,
  args_json     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS puzzles (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id        INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  idx_in_run    INTEGER NOT NULL,
  difficulty    TEXT NOT NULL,
  seed          INTEGER NOT NULL,
  clues         INTEGER NOT NULL,
  seconds       REAL    NOT NULL,
  puzzle_txt    TEXT    NOT NULL,  -- 441 chars (21x21) '.' for empty/inactive, '1'..'9' for digits
  solution_txt  TEXT    NOT NULL,
  UNIQUE(run_id, idx_in_run)
);
CREATE INDEX IF NOT EXISTS puzzles_by_run ON puzzles(run_id);
CREATE INDEX IF NOT EXISTS puzzles_by_diff ON puzzles(difficulty);
"""

def open_db(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()

def grid_to_text(g: Grid) -> str:
    # 21x21 row-major; inactive or empty => '.'
    out = []
    for r in range(21):
        for c in range(21):
            v = g[r][c]
            out.append(str(v) if isinstance(v, int) and 1 <= v <= 9 else ".")
    return "".join(out)  # len == 441

def insert_run(conn: sqlite3.Connection, *, args: Dict[str, Any], schedule: List[str]) -> int:
    mix = {
        "mix_easy":   schedule.count("easy"),
        "mix_medium": schedule.count("medium"),
        "mix_hard":   schedule.count("hard"),
        "mix_evil":   schedule.count("evil"),
    }
    row = {
        "created_utc": int(time.time()),
        "seed":        args.get("seed"),
        "pages":       len(schedule),
        "pagesize":    args.get("pagesize"),
        "uniq_timeout": float(args.get("uniq_timeout")),
        "adapt":        0 if args.get("no_adapt") else 1,
        "workers":      args.get("workers"),
        **mix,
        "args_json": json.dumps(args, ensure_ascii=False),
    }
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO runs
           (created_utc, seed, pages, pagesize, uniq_timeout, adapt, workers,
            mix_easy, mix_medium, mix_hard, mix_evil, args_json)
           VALUES (:created_utc, :seed, :pages, :pagesize, :uniq_timeout, :adapt, :workers,
                   :mix_easy, :mix_medium, :mix_hard, :mix_evil, :args_json)""",
        row,
    )
    conn.commit()
    return int(cur.lastrowid)

def insert_puzzle(conn: sqlite3.Connection, *, run_id: int, idx_in_run: int,
                  difficulty: str, seed: int, clues: int, seconds: float,
                  puzzle: Grid, solution: Grid) -> None:
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO puzzles
           (run_id, idx_in_run, difficulty, seed, clues, seconds, puzzle_txt, solution_txt)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (run_id, idx_in_run, difficulty, int(seed), int(clues), float(seconds),
         grid_to_text(puzzle), grid_to_text(solution)),
    )
    conn.commit()