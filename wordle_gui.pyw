"""Compact native desktop interface for the Wordle solver."""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox, ttk
from pathlib import Path
from typing import Iterable

from wordle_solver import (
    ABSENT,
    CORRECT,
    FEEDBACK_STATES,
    MAX_ATTEMPTS,
    PRESENT,
    WORD_LENGTH,
    WordleSession,
    load_words,
    normalize_guess,
)


STATE_APPEARANCE = {
    ABSENT: ("#787c7e", "#ffffff", "×"),
    PRESENT: ("#b59f3b", "#111111", "~"),
    CORRECT: ("#538d4e", "#ffffff", "✓"),
}
STATE_NAMES = {
    ABSENT: "Absent",
    PRESENT: "Present",
    CORRECT: "Correct",
}
STATE_ORDER = tuple(FEEDBACK_STATES)


class WordleApp(ttk.Frame):
    """Tkinter front end backed by a :class:`WordleSession`."""

    def __init__(
        self,
        master: tk.Misc,
        words: Iterable[str] | None = None,
        fallback_words: Iterable[str] | None = None,
    ) -> None:
        super().__init__(master, padding=(16, 9, 16, 10))
        self.session = WordleSession(
            load_words() if words is None else words,
            fallback_words,
        )
        self.draft_letters: list[str] = []
        self.draft_feedback = [ABSENT] * WORD_LENGTH

        self.status_var = tk.StringVar()
        self.candidate_var = tk.StringVar()
        self.preview_var = tk.StringVar()
        self.row_var = tk.StringVar()

        self._configure_styles()
        self._build_interface()
        self._bind_keyboard()
        self._render_board()
        self._update_summary()
        self._set_status(
            "Type or paste five letters, mark the tiles, then press Enter."
        )
        self.after_idle(self.focus_set)

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        style.configure("Title.Wordle.TLabel", font=("TkDefaultFont", 18, "bold"))
        style.configure("Section.Wordle.TLabel", font=("TkDefaultFont", 10, "bold"))
        style.configure("Count.Wordle.TLabel", font=("TkDefaultFont", 12, "bold"))
        style.configure("Suggestion.Wordle.TButton", font=("TkDefaultFont", 11, "bold"))
        style.configure("Primary.Wordle.TButton", font=("TkDefaultFont", 10, "bold"))

    def _build_interface(self) -> None:
        self.columnconfigure(0, weight=3)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        header.columnconfigure(0, weight=1)
        ttk.Label(
            header, text="WORDLE SOLVER", style="Title.Wordle.TLabel"
        ).grid(row=0, column=0, sticky="w")
        ttk.Button(header, text="Help", command=self._show_help).grid(
            row=0, column=1, sticky="e"
        )

        board_panel = ttk.Frame(self)
        board_panel.grid(row=1, column=0, sticky="nsew", padx=(0, 16))
        board_panel.columnconfigure(0, weight=1)

        self.board = ttk.Frame(board_panel)
        self.board.grid(row=0, column=0, sticky="n")
        self.tiles: list[list[tk.Button]] = []
        tile_font = tkfont.nametofont("TkDefaultFont").copy()
        tile_font.configure(size=14, weight="bold")

        for row in range(MAX_ATTEMPTS):
            tile_row: list[tk.Button] = []
            for column in range(WORD_LENGTH):
                tile = tk.Button(
                    self.board,
                    width=4,
                    height=2,
                    font=tile_font,
                    takefocus=False,
                    padx=0,
                    pady=0,
                    bd=2,
                    highlightthickness=1,
                    highlightbackground="#d3d6da",
                    highlightcolor="#1a73e8",
                    relief="groove",
                    command=lambda r=row, c=column: self._cycle_tile(r, c),
                )
                tile.bind(
                    "<Return>",
                    lambda event, r=row, c=column: self._activate_tile_key(r, c),
                )
                tile.bind(
                    "<KP_Enter>",
                    lambda event, r=row, c=column: self._activate_tile_key(r, c),
                )
                tile.grid(row=row, column=column, padx=3, pady=2, sticky="nsew")
                tile_row.append(tile)
            self.tiles.append(tile_row)

        ttk.Label(
            board_panel,
            text="× Absent (gray)   ~ Present (yellow)   ✓ Correct (green)",
            anchor="center",
            justify="center",
            wraplength=350,
        ).grid(row=1, column=0, sticky="ew", pady=(4, 1))
        ttk.Label(
            board_panel,
            text="Click a tile, or focus it with Tab and press Space/Enter.",
            anchor="center",
            foreground="#555555",
        ).grid(row=2, column=0, sticky="ew")

        side = ttk.Frame(self)
        side.grid(row=1, column=1, sticky="nsew")
        side.columnconfigure(0, weight=1)

        ttk.Label(side, textvariable=self.row_var, style="Section.Wordle.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(side, textvariable=self.candidate_var, style="Count.Wordle.TLabel").grid(
            row=1, column=0, sticky="w", pady=(4, 2)
        )
        ttk.Label(
            side,
            textvariable=self.preview_var,
            justify="left",
            wraplength=240,
            foreground="#454545",
        ).grid(row=2, column=0, sticky="ew", pady=(0, 14))

        ttk.Label(side, text="RECOMMENDATIONS", style="Section.Wordle.TLabel").grid(
            row=3, column=0, sticky="w", pady=(0, 5)
        )
        self.suggestion_buttons: list[ttk.Button] = []
        for index in range(5):
            button = ttk.Button(
                side,
                text="—",
                style="Suggestion.Wordle.TButton",
                command=lambda i=index: self._use_suggestion(i),
            )
            button.grid(row=4 + index, column=0, sticky="ew", pady=2)
            self.suggestion_buttons.append(button)
        self._suggestion_words: list[str] = []

        controls = ttk.Frame(self)
        controls.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 6))
        controls.columnconfigure(0, weight=1)
        controls.columnconfigure(1, weight=1)
        controls.columnconfigure(2, weight=1)
        self.submit_button = ttk.Button(
            controls,
            text="Submit",
            style="Primary.Wordle.TButton",
            command=self._submit,
        )
        self.submit_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.undo_button = ttk.Button(
            controls, text="Undo Last", command=self._undo
        )
        self.undo_button.grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(controls, text="Reset", command=self._reset).grid(
            row=0, column=2, sticky="ew", padx=(4, 0)
        )

        self.status_label = tk.Label(
            self,
            textvariable=self.status_var,
            anchor="w",
            justify="left",
            wraplength=610,
            padx=9,
            pady=5,
            bg="#edf2f7",
            fg="#263238",
        )
        self.status_label.grid(row=3, column=0, columnspan=2, sticky="ew")

    def _bind_keyboard(self) -> None:
        top = self.winfo_toplevel()
        top.bind("<KeyPress>", self._on_keypress, add="+")
        top.bind("<<Paste>>", self._paste, add="+")
        if self.tk.call("tk", "windowingsystem") == "aqua":
            top.bind("<Command-v>", self._paste, add="+")
            top.bind("<Command-V>", self._paste, add="+")
            top.bind("<Meta-v>", self._paste, add="+")
            top.bind("<Meta-V>", self._paste, add="+")
        self.configure(takefocus=True)

    def _active_row(self) -> int | None:
        if self.session.is_over:
            return None
        return len(self.session.attempts)

    def _on_keypress(self, event: tk.Event) -> str | None:
        # Tk's modifier masks vary by windowing system.  Mod1 is 0x8 on
        # X11, while Windows reports Alt as 0x20000.
        modified = event.state & (0x4 | 0x8 | 0x20000)
        if self.tk.call("tk", "windowingsystem") == "aqua":
            modified |= event.state & 0x10  # Command on macOS.
        if modified:
            return None
        if event.keysym in ("Return", "KP_Enter"):
            self._submit()
            return "break"
        if event.keysym == "BackSpace":
            self._backspace()
            return "break"
        character = event.char
        if character and character.isascii() and character.isalpha():
            self._append_letters(character)
            return "break"
        return None

    def _activate_tile_key(self, row: int, column: int) -> str:
        """Cycle a focused tile with Enter; Space uses Tk's button binding."""

        self._cycle_tile(row, column)
        return "break"

    def _paste(self, _event: tk.Event | None = None) -> str:
        if self.session.is_over:
            self._set_status("This session is finished. Undo or reset to continue.", error=True)
            return "break"
        try:
            clipboard = self.clipboard_get()
        except tk.TclError:
            self._set_status("The clipboard does not contain text.", error=True)
            return "break"
        letters = "".join(
            character
            for character in clipboard
            if character.isascii() and character.isalpha()
        )
        if not letters:
            self._set_status("Paste text must contain ASCII letters.", error=True)
            return "break"
        self._append_letters(letters)
        return "break"

    def _append_letters(self, letters: str) -> None:
        if self.session.is_over:
            self._set_status("This session is finished. Undo or reset to continue.", error=True)
            return
        available = WORD_LENGTH - len(self.draft_letters)
        if available <= 0:
            self._set_status("The active row already has five letters.", error=True)
            return
        accepted = [letter.lower() for letter in letters[:available]]
        start = len(self.draft_letters)
        self.draft_letters.extend(accepted)
        for index in range(start, len(self.draft_letters)):
            self.draft_feedback[index] = ABSENT
        self._render_board()
        if len(letters) > available:
            self._set_status("Only the first five letters fit in the active row.", error=True)
        elif len(self.draft_letters) == WORD_LENGTH:
            self._set_status("Guess complete. Mark feedback, then press Enter.")
        else:
            self._set_status(f"{len(self.draft_letters)} of {WORD_LENGTH} letters entered.")

    def _backspace(self) -> None:
        if self.session.is_over:
            self._set_status("This session is finished. Undo or reset to continue.", error=True)
            return
        if not self.draft_letters:
            self._set_status("The active row is already empty.", error=True)
            return
        index = len(self.draft_letters) - 1
        self.draft_letters.pop()
        self.draft_feedback[index] = ABSENT
        self._render_board()
        self._set_status(f"{len(self.draft_letters)} of {WORD_LENGTH} letters entered.")

    def _cycle_tile(self, row: int, column: int) -> None:
        if row != self._active_row() or column >= len(self.draft_letters):
            self.focus_set()
            return
        current = self.draft_feedback[column]
        next_index = (STATE_ORDER.index(current) + 1) % len(STATE_ORDER)
        self.draft_feedback[column] = STATE_ORDER[next_index]
        self._render_board()
        state = self.draft_feedback[column]
        self._set_status(
            f"Tile {column + 1} is {STATE_NAMES[state].lower()} "
            f"({STATE_APPEARANCE[state][2]})."
        )
        self.tiles[row][column].focus_set()

    def _submit(self) -> None:
        if self.session.is_over:
            self._set_status("This session is finished. Undo or reset to continue.", error=True)
            return
        try:
            guess = normalize_guess("".join(self.draft_letters))
        except ValueError:
            self._set_status("Enter exactly five ASCII letters before submitting.", error=True)
            return
        try:
            self.session.submit(guess, tuple(self.draft_feedback))
        except (RuntimeError, ValueError) as exc:
            self._set_status(str(exc).capitalize(), error=True)
            return

        self.draft_letters.clear()
        self.draft_feedback = [ABSENT] * WORD_LENGTH
        self._render_board()
        self._update_summary()
        if self.session.solved:
            self._set_status(f"Solved! {guess.upper()} is marked all correct.", success=True)
        elif self.session.exhausted:
            self._set_status(
                "Six attempts used without an all-correct row. Undo or reset to continue.",
                error=True,
            )
        elif self.session.candidate_count == 0:
            self._set_status(
                "No bundled candidates match. Check the feedback, then undo "
                "the last row if it needs correction.",
                error=True,
            )
        elif self.session.using_fallback:
            self._set_status(
                "No common-list answers matched, so suggestions expanded to "
                "the broader Wordle vocabulary."
            )
        else:
            self._set_status(
                f"Feedback applied. Continue with attempt {self.session.attempt_number}."
            )
        self.focus_set()

    def _undo(self) -> None:
        attempt = self.session.undo()
        if attempt is None:
            self._set_status("There is no submitted guess to undo.", error=True)
            self.focus_set()
            return
        self.draft_letters = list(attempt.guess)
        self.draft_feedback = list(attempt.feedback)
        self._render_board()
        self._update_summary()
        self._set_status(
            f"Restored {attempt.guess.upper()} with its marks for correction."
        )
        self.focus_set()

    def _reset(self) -> None:
        if (self.session.attempts or self.draft_letters) and not messagebox.askyesno(
            "Reset session?",
            "Clear all submitted guesses and the current draft, then start again?",
            parent=self.winfo_toplevel(),
        ):
            self.after_idle(self.focus_set)
            return
        self.session.reset()
        self.draft_letters.clear()
        self.draft_feedback = [ABSENT] * WORD_LENGTH
        self._render_board()
        self._update_summary()
        self._set_status("Session reset. Enter a new five-letter guess.")
        self.focus_set()

    def _use_suggestion(self, index: int) -> None:
        if self.session.is_over or index >= len(self._suggestion_words):
            self.focus_set()
            return
        word = self._suggestion_words[index]
        self.draft_letters = list(word)
        self.draft_feedback = [ABSENT] * WORD_LENGTH
        self._render_board()
        self._set_status(f"Filled {word.upper()}. Mark feedback, then press Enter.")
        self.focus_set()

    def _render_board(self) -> None:
        attempts = self.session.attempts
        active_row = self._active_row()
        for row, tile_row in enumerate(self.tiles):
            if row < len(attempts):
                letters = list(attempts[row].guess)
                feedback = list(attempts[row].feedback)
            elif row == active_row:
                letters = self.draft_letters
                feedback = self.draft_feedback
            else:
                letters = []
                feedback = []

            for column, tile in enumerate(tile_row):
                if column < len(letters):
                    state = feedback[column]
                    background, foreground, symbol = STATE_APPEARANCE[state]
                    tile.configure(
                        text=f"{letters[column].upper()}\n{symbol}",
                        bg=background,
                        fg=foreground,
                        activebackground=background,
                        activeforeground=foreground,
                        disabledforeground=foreground,
                        relief="raised" if row == active_row else "flat",
                        cursor="hand2" if row == active_row else "arrow",
                        takefocus=bool(row == active_row),
                    )
                else:
                    active = row == active_row
                    background = "#ffffff" if active else "#f2f3f4"
                    tile.configure(
                        text="",
                        bg=background,
                        fg="#202124",
                        activebackground=background,
                        activeforeground="#202124",
                        disabledforeground="#202124",
                        relief="groove",
                        cursor="arrow",
                        takefocus=False,
                    )
        self.submit_button.state(["disabled"] if self.session.is_over else ["!disabled"])
        self.undo_button.state(["!disabled"] if attempts else ["disabled"])
        if self.session.is_over:
            self.row_var.set("SESSION COMPLETE")
        else:
            self.row_var.set(f"ATTEMPT {self.session.attempt_number} OF {MAX_ATTEMPTS}")

    def _update_summary(self) -> None:
        count = self.session.candidate_count
        noun = "candidate" if count == 1 else "candidates"
        qualifier = " (expanded)" if self.session.using_fallback else ""
        self.candidate_var.set(f"{count:,} {noun}{qualifier}")
        preview = self.session.remaining_words[:10]
        if preview:
            suffix = " …" if count > len(preview) else ""
            self.preview_var.set("Preview: " + ", ".join(preview).upper() + suffix)
        else:
            self.preview_var.set("Preview: none")

        suggestions = list(self.session.suggestions(limit=5))
        self._suggestion_words = [word for word, _score in suggestions]
        for index, button in enumerate(self.suggestion_buttons):
            if index < len(suggestions):
                word, _score = suggestions[index]
                button.configure(text=word.upper())
                button.state(["disabled"] if self.session.is_over else ["!disabled"])
            else:
                button.configure(text="—")
                button.state(["disabled"])

    def _set_status(
        self, message: str, *, error: bool = False, success: bool = False
    ) -> None:
        if success:
            colors = ("#e5f4e3", "#255b24")
        elif error:
            colors = ("#fdeceb", "#8b1e1e")
        else:
            colors = ("#edf2f7", "#263238")
        self.status_var.set(message)
        self.status_label.configure(bg=colors[0], fg=colors[1])

    def _show_help(self) -> None:
        messagebox.showinfo(
            "How to use Wordle Solver",
            "Type or paste a five-letter guess into the active row.\n\n"
            "Click each filled tile to cycle its feedback, or use Tab to "
            "focus a tile and press Space/Enter:\n"
            "  × Absent (gray)\n"
            "  ~ Present elsewhere (yellow)\n"
            "  ✓ Correct position (green)\n\n"
            "Untouched tiles start as absent. Press Enter to submit and "
            "Backspace to edit. Submitted rows are locked; use Undo Last "
            "to restore the newest row and its marks.",
            parent=self.winfo_toplevel(),
        )
        self.after_idle(self.focus_set)


def main() -> None:
    root = tk.Tk()
    root.withdraw()
    root.title("Wordle Solver")
    try:
        words = load_words()
        valid_path = Path(__file__).with_name("valid_words.txt")
        fallback_words = load_words(valid_path) if valid_path.exists() else ()
    except (OSError, ValueError) as exc:
        messagebox.showerror(
            "Word list error",
            "Wordle Solver could not load its word list.\n\n" + str(exc),
            parent=root,
        )
        root.destroy()
        return

    app = WordleApp(root, words, fallback_words)
    app.grid(row=0, column=0, sticky="nsew")
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    root.update_idletasks()
    initial_width = max(670, root.winfo_reqwidth())
    initial_height = max(660, root.winfo_reqheight())
    root.geometry(f"{initial_width}x{initial_height}")
    root.minsize(max(560, root.winfo_reqwidth()), root.winfo_reqheight())
    root.deiconify()
    root.update_idletasks()
    x = max(0, (root.winfo_screenwidth() - root.winfo_width()) // 2)
    y = max(0, (root.winfo_screenheight() - root.winfo_height()) // 3)
    root.geometry(f"+{x}+{y}")
    app.focus_set()
    root.mainloop()


if __name__ == "__main__":
    main()
