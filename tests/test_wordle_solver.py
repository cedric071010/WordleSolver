import tempfile
import unittest
from collections import Counter
from pathlib import Path

from wordle_solver import (
    ABSENT,
    CORRECT,
    MAX_ATTEMPTS,
    PRESENT,
    WORD_LENGTH,
    Attempt,
    WordleSession,
    count_letters,
    evaluate_guess,
    filter_candidates,
    load_words,
    normalize_guess,
    rank_words,
    score_word,
)


class WordValidationTests(unittest.TestCase):
    def test_public_game_dimensions(self):
        self.assertEqual(WORD_LENGTH, 5)
        self.assertEqual(MAX_ATTEMPTS, 6)

    def test_normalize_guess_strips_and_lowercases(self):
        self.assertEqual(normalize_guess("  CRANE\n"), "crane")

    def test_normalize_guess_rejects_non_words(self):
        for value in ("", "four", "longer", "ab1de", "a-bcd", "cafés"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalize_guess(value)

        with self.assertRaises((TypeError, ValueError)):
            normalize_guess(None)

    def test_load_words_normalizes_deduplicates_and_skips_invalid_lines(self):
        contents = " CRANE \nslate\ncrane\n\nab1de\ntoolong\nAPPLE\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "words.txt")
            path.write_text(contents, encoding="utf-8")

            self.assertEqual(load_words(path), ("crane", "slate", "apple"))

    def test_load_words_rejects_missing_or_empty_word_lists(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory, "missing.txt")
            empty = Path(directory, "empty.txt")
            empty.write_text("\ninvalid\nab1de\n", encoding="utf-8")

            with self.assertRaises((FileNotFoundError, ValueError)):
                load_words(missing)
            with self.assertRaises(ValueError):
                load_words(empty)

    def test_default_answer_pool_is_curated_and_module_relative(self):
        words = load_words()

        self.assertEqual(len(words), 2315)
        self.assertEqual(words[0], "aback")
        self.assertEqual(words[-1], "zonal")
        self.assertNotIn("aahed", words)


class FeedbackTests(unittest.TestCase):
    def test_attempt_normalizes_guess_and_stores_feedback(self):
        feedback = (ABSENT, PRESENT, CORRECT, ABSENT, PRESENT)
        self.assertEqual(Attempt(" CRANE ", feedback), Attempt("crane", feedback))

    def test_attempt_rejects_invalid_guess_or_feedback(self):
        invalid_attempts = [
            ("bad", (ABSENT,) * WORD_LENGTH),
            ("crane", (ABSENT,) * (WORD_LENGTH - 1)),
            ("crane", (ABSENT,) * WORD_LENGTH + (ABSENT,)),
            ("crane", (ABSENT, ABSENT, ABSENT, ABSENT, "not-feedback")),
        ]
        for guess, feedback in invalid_attempts:
            with self.subTest(guess=guess, feedback=feedback):
                with self.assertRaises(ValueError):
                    Attempt(guess, feedback)

    def test_evaluate_guess_all_three_feedback_states(self):
        self.assertEqual(
            evaluate_guess("cigar", "crane"),
            (CORRECT, PRESENT, PRESENT, ABSENT, ABSENT),
        )

    def test_evaluate_guess_all_correct(self):
        self.assertEqual(evaluate_guess("apple", "apple"), (CORRECT,) * 5)

    def test_evaluate_guess_allocates_duplicate_letters_only_once(self):
        # The first non-green l consumes the answer's only remaining l; the
        # second l is absent. The final e is reserved by its green match.
        self.assertEqual(
            evaluate_guess("apple", "allee"),
            (CORRECT, PRESENT, ABSENT, ABSENT, CORRECT),
        )

    def test_evaluate_guess_validates_both_words(self):
        for answer, guess in (("bad", "crane"), ("crane", "bad"), ("crane", "a1b2c")):
            with self.subTest(answer=answer, guess=guess):
                with self.assertRaises(ValueError):
                    evaluate_guess(answer, guess)


class CandidateFilteringTests(unittest.TestCase):
    WORDS = ["apple", "ample", "angle", "papal", "cigar", "spore"]

    def test_filter_candidates_requires_the_exact_feedback_pattern(self):
        attempt = Attempt("aaaaa", (CORRECT, ABSENT, ABSENT, ABSENT, ABSENT))

        self.assertEqual(filter_candidates(self.WORDS, [attempt]), ("apple", "ample", "angle"))

    def test_filter_candidates_combines_multiple_attempts(self):
        attempts = [
            Attempt("aaaaa", (CORRECT, ABSENT, ABSENT, ABSENT, ABSENT)),
            Attempt("poppy", (PRESENT, ABSENT, CORRECT, ABSENT, ABSENT)),
        ]

        self.assertEqual(filter_candidates(self.WORDS, attempts), ("apple",))

    def test_filter_candidates_with_no_attempts_preserves_words(self):
        self.assertEqual(filter_candidates(self.WORDS, []), tuple(self.WORDS))


class ScoringTests(unittest.TestCase):
    def test_count_letters_counts_presence_and_duplicate_thresholds(self):
        self.assertEqual(
            count_letters(["apple", "ample", "cigar"]),
            Counter({"a": 3, "p": 2, "l": 2, "e": 2, "p2": 1, "m": 1, "c": 1, "i": 1, "g": 1, "r": 1}),
        )

    def test_score_word_scores_each_distinct_letter_once(self):
        letter_counts = Counter({"a": 10, "p": 4, "l": 3, "e": 2})
        self.assertEqual(score_word("apple", letter_counts), 19)

    def test_rank_words_orders_by_score_then_alphabetically_and_honors_limit(self):
        words = ["afghi", "jklmn", "abcde"]
        expected = (("abcde", 6), ("afghi", 6), ("jklmn", 5))
        self.assertEqual(rank_words(words), expected)
        self.assertEqual(rank_words(words, limit=2), expected[:2])
        self.assertEqual(rank_words(words, limit=0), ())

    def test_rank_words_rejects_invalid_limits(self):
        for limit in (-1, 1.5, True):
            with self.subTest(limit=limit):
                with self.assertRaises(ValueError):
                    rank_words(["crane"], limit=limit)


class WordleSessionTests(unittest.TestCase):
    WORDS = ["apple", "ample", "angle", "papal", "cigar", "spore"]
    FIRST_FEEDBACK = (CORRECT, ABSENT, ABSENT, ABSENT, ABSENT)
    SECOND_FEEDBACK = (PRESENT, ABSENT, CORRECT, ABSENT, ABSENT)

    def test_new_session_exposes_initial_state_and_suggestions(self):
        session = WordleSession(self.WORDS)

        self.assertEqual(session.remaining_words, tuple(self.WORDS))
        self.assertEqual(session.attempts, ())
        self.assertEqual(session.candidate_count, len(self.WORDS))
        self.assertEqual(session.attempt_number, 1)
        self.assertFalse(session.solved)
        self.assertFalse(session.exhausted)
        self.assertFalse(session.is_over)
        self.assertLessEqual(len(session.suggestions()), 5)

    def test_submit_filters_candidates_and_records_attempt(self):
        session = WordleSession(self.WORDS)
        session.submit("AAAAA", self.FIRST_FEEDBACK)

        self.assertEqual(session.remaining_words, ("apple", "ample", "angle"))
        self.assertEqual(session.candidate_count, 3)
        self.assertEqual(session.attempt_number, 2)
        self.assertEqual(session.attempts, (Attempt("aaaaa", self.FIRST_FEEDBACK),))

    def test_undo_recomputes_from_all_previous_attempts(self):
        session = WordleSession(self.WORDS)
        session.submit("aaaaa", self.FIRST_FEEDBACK)
        session.submit("poppy", self.SECOND_FEEDBACK)
        self.assertEqual(session.remaining_words, ("apple",))

        session.undo()

        self.assertEqual(session.remaining_words, ("apple", "ample", "angle"))
        self.assertEqual(session.candidate_count, 3)
        self.assertEqual(session.attempt_number, 2)
        self.assertEqual(len(session.attempts), 1)

    def test_undo_on_new_session_is_a_safe_noop(self):
        session = WordleSession(self.WORDS)
        session.undo()
        self.assertEqual(session.remaining_words, tuple(self.WORDS))
        self.assertEqual(session.attempt_number, 1)

    def test_reset_restores_complete_initial_state(self):
        session = WordleSession(self.WORDS)
        session.submit("aaaaa", self.FIRST_FEEDBACK)

        session.reset()

        self.assertEqual(session.remaining_words, tuple(self.WORDS))
        self.assertEqual(session.attempts, ())
        self.assertEqual(session.attempt_number, 1)
        self.assertFalse(session.is_over)

    def test_session_expands_to_broader_words_when_common_pool_is_empty(self):
        session = WordleSession(("apple", "ample"), ("guano", "aahed"))
        feedback = evaluate_guess("guano", "audio")

        session.submit("audio", feedback)

        self.assertEqual(session.remaining_words, ("guano",))
        self.assertTrue(session.using_fallback)

        session.undo()

        self.assertEqual(session.remaining_words, ("apple", "ample"))
        self.assertFalse(session.using_fallback)

    def test_all_correct_feedback_solves_and_blocks_more_submissions(self):
        session = WordleSession(self.WORDS)
        session.submit("apple", (CORRECT,) * WORD_LENGTH)

        self.assertTrue(session.solved)
        self.assertTrue(session.is_over)
        self.assertFalse(session.exhausted)
        self.assertEqual(session.remaining_words, ("apple",))
        with self.assertRaises(RuntimeError):
            session.submit("cigar", (ABSENT,) * WORD_LENGTH)

    def test_six_unsolved_attempts_exhaust_session_and_seventh_is_blocked(self):
        session = WordleSession(self.WORDS)
        for guess in ("bbbbb", "ddddd", "fffff", "hhhhh", "jjjjj", "kkkkk"):
            session.submit(guess, (ABSENT,) * WORD_LENGTH)

        self.assertEqual(len(session.attempts), MAX_ATTEMPTS)
        self.assertEqual(session.attempt_number, MAX_ATTEMPTS)
        self.assertTrue(session.exhausted)
        self.assertTrue(session.is_over)
        self.assertFalse(session.solved)
        with self.assertRaises(RuntimeError):
            session.submit("mmmmm", (ABSENT,) * WORD_LENGTH)

    def test_submit_rejects_bad_guess_without_changing_state(self):
        session = WordleSession(self.WORDS)
        for guess in ("bad", "ab1de"):
            with self.subTest(guess=guess):
                with self.assertRaises(ValueError):
                    session.submit(guess, (ABSENT,) * WORD_LENGTH)
        self.assertEqual(session.attempts, ())
        self.assertEqual(session.remaining_words, tuple(self.WORDS))

    def test_submit_rejects_invalid_feedback_without_changing_state(self):
        session = WordleSession(self.WORDS)
        invalid_feedback = [
            (ABSENT,) * (WORD_LENGTH - 1),
            (ABSENT,) * WORD_LENGTH + (ABSENT,),
            (ABSENT, ABSENT, ABSENT, ABSENT, "not-feedback"),
        ]
        for feedback in invalid_feedback:
            with self.subTest(feedback=feedback):
                with self.assertRaises(ValueError):
                    session.submit("crane", feedback)
        self.assertEqual(session.attempts, ())
        self.assertEqual(session.remaining_words, tuple(self.WORDS))


if __name__ == "__main__":
    unittest.main()
