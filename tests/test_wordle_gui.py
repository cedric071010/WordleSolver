import importlib.util
import tkinter as tk
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import SimpleNamespace


GUI_PATH = Path(__file__).resolve().parents[1] / "wordle_gui.pyw"
GUI_LOADER = SourceFileLoader("wordle_gui", str(GUI_PATH))
GUI_SPEC = importlib.util.spec_from_loader(GUI_LOADER.name, GUI_LOADER)
if GUI_SPEC is None:
    raise ImportError(f"Cannot create an import specification for {GUI_PATH}")
wordle_gui = importlib.util.module_from_spec(GUI_SPEC)
GUI_LOADER.exec_module(wordle_gui)


class WordleGuiTests(unittest.TestCase):
    WORDS = ("apple", "ample", "angle", "papal", "cigar", "spore")

    def setUp(self):
        self.root = None
        try:
            self.root = tk.Tk()
            self.addCleanup(self._destroy_root)
            self.root.withdraw()
            self.app = wordle_gui.WordleApp(self.root, self.WORDS)
            self.app.grid(row=0, column=0)
            self.root.update_idletasks()
        except tk.TclError as exc:
            self.skipTest(f"Tk is unavailable: {exc}")

    def _destroy_root(self):
        if self.root is not None:
            try:
                self.root.destroy()
            except tk.TclError:
                pass
            self.root = None

    def _type(self, letters):
        for letter in letters:
            event = SimpleNamespace(state=0, keysym=letter, char=letter)
            self.assertEqual(self.app._on_keypress(event), "break")

    def _is_disabled(self, widget):
        return "disabled" in widget.state()

    def _is_focusable(self, widget):
        return self.root.tk.getboolean(widget.cget("takefocus"))

    def test_board_has_six_rows_of_five_tiles_and_typing_fills_active_row(self):
        self.assertEqual(len(self.app.tiles), 6)
        self.assertTrue(all(len(row) == 5 for row in self.app.tiles))

        self._type("CrAnE")

        self.assertEqual(self.app.draft_letters, list("crane"))
        self.assertEqual(
            [tile.cget("text").splitlines()[0] for tile in self.app.tiles[0]],
            list("CRANE"),
        )
        self.assertTrue(all(self._is_focusable(tile) for tile in self.app.tiles[0]))
        self.assertTrue(all(not self._is_focusable(tile) for tile in self.app.tiles[1]))

    def test_filled_tile_is_keyboard_activatable_and_cycles_all_feedback(self):
        self._type("apple")
        tile = self.app.tiles[0][0]

        self.assertTrue(self._is_focusable(tile))
        self.assertTrue(tile.bind("<Return>"))
        for expected_state in (
            wordle_gui.PRESENT,
            wordle_gui.CORRECT,
            wordle_gui.ABSENT,
        ):
            self.assertEqual(self.app._activate_tile_key(0, 0), "break")
            self.assertEqual(self.app.draft_feedback[0], expected_state)
            self.assertEqual(
                tile.cget("bg"), wordle_gui.STATE_APPEARANCE[expected_state][0]
            )

    def test_modified_letter_shortcuts_do_not_edit_the_draft(self):
        for state in (0x4, 0x8, 0x20000):  # Control, X11 Mod1, Windows Alt
            with self.subTest(state=state):
                event = SimpleNamespace(state=state, keysym="x", char="x")
                self.assertIsNone(self.app._on_keypress(event))

        self.assertEqual(self.app.draft_letters, [])

    def test_submit_locks_row_and_updates_candidates_and_controls(self):
        self._type("aaaaa")
        self.app._activate_tile_key(0, 0)
        self.app._activate_tile_key(0, 0)

        self.app._submit()

        self.assertEqual(self.app.session.candidate_count, 3)
        self.assertEqual(self.app.session.remaining_words, ("apple", "ample", "angle"))
        self.assertEqual(self.app.candidate_var.get(), "3 candidates")
        self.assertEqual(self.app.row_var.get(), "ATTEMPT 2 OF 6")
        self.assertTrue(all(not self._is_focusable(tile) for tile in self.app.tiles[0]))
        self.assertFalse(self._is_disabled(self.app.submit_button))
        self.assertFalse(self._is_disabled(self.app.undo_button))

    def test_undo_restores_guess_feedback_and_tile_colors(self):
        feedback = (
            wordle_gui.PRESENT,
            wordle_gui.CORRECT,
            wordle_gui.ABSENT,
            wordle_gui.PRESENT,
            wordle_gui.CORRECT,
        )
        self._type("crane")
        for column, state in enumerate(feedback):
            for _ in range(wordle_gui.STATE_ORDER.index(state)):
                self.app._cycle_tile(0, column)
        self.app._submit()

        self.app._undo()

        self.assertEqual(self.app.session.attempts, ())
        self.assertEqual(self.app.draft_letters, list("crane"))
        self.assertEqual(tuple(self.app.draft_feedback), feedback)
        self.assertEqual(self.app.session.candidate_count, len(self.WORDS))
        for tile, state in zip(self.app.tiles[0], feedback):
            self.assertEqual(tile.cget("bg"), wordle_gui.STATE_APPEARANCE[state][0])
            self.assertTrue(self._is_focusable(tile))

    def test_solved_session_disables_submit_and_suggestions(self):
        self._type("apple")
        for column in range(5):
            self.app._cycle_tile(0, column)
            self.app._cycle_tile(0, column)

        self.app._submit()

        self.assertTrue(self.app.session.solved)
        self.assertEqual(self.app.row_var.get(), "SESSION COMPLETE")
        self.assertTrue(self._is_disabled(self.app.submit_button))
        self.assertFalse(self._is_disabled(self.app.undo_button))
        self.assertTrue(all(self._is_disabled(button) for button in self.app.suggestion_buttons))
        self.assertIn("Solved!", self.app.status_var.get())

    def test_six_unsolved_rows_exhaust_session_and_disable_controls(self):
        for guess in ("qqqqq", "bbbbb", "ddddd", "fffff", "hhhhh", "jjjjj"):
            self._type(guess)
            self.app._submit()

        self.assertTrue(self.app.session.exhausted)
        self.assertEqual(len(self.app.session.attempts), 6)
        self.assertEqual(self.app.row_var.get(), "SESSION COMPLETE")
        self.assertTrue(self._is_disabled(self.app.submit_button))
        self.assertFalse(self._is_disabled(self.app.undo_button))
        self.assertTrue(all(self._is_disabled(button) for button in self.app.suggestion_buttons))
        self.assertIn("Six attempts used", self.app.status_var.get())

    def test_zero_candidate_feedback_is_recoverable_with_undo(self):
        self._type("zzzzz")
        self.app._cycle_tile(0, 0)
        self.app._submit()

        self.assertEqual(self.app.session.candidate_count, 0)
        self.assertEqual(self.app.candidate_var.get(), "0 candidates")
        self.assertEqual(self.app.preview_var.get(), "Preview: none")
        self.assertIn("No bundled candidates", self.app.status_var.get())

        self.app._undo()

        self.assertEqual(self.app.session.candidate_count, len(self.WORDS))
        self.assertEqual(self.app.draft_letters, list("zzzzz"))
        self.assertEqual(
            tuple(self.app.draft_feedback),
            (wordle_gui.PRESENT,) + (wordle_gui.ABSENT,) * 4,
        )
        self.assertEqual(self.app.row_var.get(), "ATTEMPT 1 OF 6")
        self.assertFalse(self._is_disabled(self.app.submit_button))

    def test_expanded_candidate_pool_is_clearly_labeled(self):
        self.app.destroy()
        self.app = wordle_gui.WordleApp(
            self.root,
            ("apple", "ample"),
            ("guano", "aahed"),
        )
        self.app.grid(row=0, column=0)
        self.root.update_idletasks()
        self.app.draft_letters = list("audio")
        self.app.draft_feedback = [
            wordle_gui.PRESENT,
            wordle_gui.CORRECT,
            wordle_gui.ABSENT,
            wordle_gui.ABSENT,
            wordle_gui.CORRECT,
        ]

        self.app._submit()

        self.assertEqual(self.app.session.remaining_words, ("guano",))
        self.assertTrue(self.app.session.using_fallback)
        self.assertEqual(self.app.candidate_var.get(), "1 candidate (expanded)")
        self.assertIn("broader Wordle vocabulary", self.app.status_var.get())


if __name__ == "__main__":
    unittest.main()
