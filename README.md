# Wordle Solver

A small, no-dependency desktop helper for narrowing down Wordle answers. The
interface uses Python's bundled standard-library Tkinter toolkit and local
word lists.

## Requirements

- Python 3.10 or newer
- Tkinter (included with standard Python installations)

## Run

On Windows, double-click `wordle_gui.pyw` or run:

```powershell
py wordle_gui.pyw
```

On other platforms, run:

```shell
python wordle_gui.pyw
```

Keep `possible_words.txt` in the same directory as the application. It is the
curated 2,315-word answer pool used for candidate counts and recommendations;
`valid_words.txt` retains the project's original, broader vocabulary for
customization. The GUI accepts any five ASCII letters as a guess so newer
Wordle vocabulary is not rejected locally.

The solver starts with the common answer pool for useful recommendations. If
those candidates reach zero, it automatically checks the broader 14,855-word
vocabulary for newer or unusual answers and labels the result as **expanded**.

## Use

The board provides six guesses of five letters each. Type or paste a guess,
then click each tile to cycle its feedback state:

1. Gray: letter is absent
2. Yellow: letter is present in another position
3. Green: letter is correct in this position

Untouched tiles are treated as gray. Press Enter or click **Submit** to apply
the row. Suggestions update with the candidate count and candidate list, and
you can click a suggestion to fill the current row. Use **Undo Last** to remove
the most recent submitted guess or **Reset** to start over.

Repeated letters are evaluated positionally, so duplicate-letter guesses are
filtered according to the feedback assigned to each tile. All interaction is
keyboard-friendly: use Tab to focus a filled tile, then Space or Enter to
cycle its feedback.

## Word-list attribution

The answer pool in `possible_words.txt` is based on the 2,315-answer list from
[joshstephenson/Wordle-Solver](https://github.com/joshstephenson/Wordle-Solver/blob/48c32e1ac0cb1ec87740cab009214e89b2c636c8/nyt-answers.txt),
which is published under the MIT License. Wordle is a trademark of The New
York Times Company; this project is independent and is not endorsed by it.
The broader `valid_words.txt` list matches
[tabatkins/wordle-list](https://github.com/tabatkins/wordle-list), also
published under the MIT License. Full notices are in
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## Tests

```shell
python -m unittest discover -s tests -v
```
