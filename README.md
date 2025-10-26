# Samurai Sudoku Generator

Generate **Samurai Sudoku** (five overlapping 9×9) and export to **PDF** with:
- Difficulty labels: Easy ★, Medium ★★, Hard ★★★, Evil ★★★★
- A4 default + supports Letter/Legal
- N pages of puzzles, then a compact **Solutions** section

## Install
~~~bash
conda create -n samurai-sudoku python=3.11 -y
conda activate samurai-sudoku
pip install -r requirements.txt
pip install -e .
~~~

## Usage

~~~bash
samurai-sudoku --easy 4 --medium 3 --hard 2 --evil 1 --workers 4 --seed 58966 --uniq-timeout 6 --outfile book_mix.pdf
~~~

## Options

- --pages (int): how many puzzles to generate

- --difficulty: (easy|medium|hard|evil)

- --outfile: path to PDF 

- --pagesize: (A4|LETTER|LEGAL)

- --seed (int): Master random seed for reproducibility

- --workers: Number of parallel worker processes.

## Notes

Difficulty is approximated via target clue counts + uniqueness check.

Runtime depends on difficulty/pages (evil can be slower).