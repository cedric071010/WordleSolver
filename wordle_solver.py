"""Pure Wordle solving primitives and session state.

The module has no user-interface or persistence side effects, so it can be
safely imported by a desktop application or a test suite.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence


WORD_LENGTH = 5
MAX_ATTEMPTS = 6

ABSENT = "absent"
PRESENT = "present"
CORRECT = "correct"
FEEDBACK_STATES = (ABSENT, PRESENT, CORRECT)


def normalize_guess(value: str) -> str:
    """Return a lowercase five-letter ASCII word.

    ``ValueError`` is used for every invalid input so callers can present a
    single, consistent validation message.
    """

    if not isinstance(value, str):
        raise ValueError("guess must be exactly five ASCII letters")
    value = value.strip()
    if (
        len(value) != WORD_LENGTH
        or not value.isascii()
        or not value.isalpha()
    ):
        raise ValueError("guess must be exactly five ASCII letters")
    return value.lower()


@dataclass(frozen=True)
class Attempt:
    """One normalized guess and its five corresponding feedback states."""

    guess: str
    feedback: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "guess", normalize_guess(self.guess))
        try:
            feedback = tuple(self.feedback)
        except TypeError as exc:
            raise ValueError("feedback must contain exactly five states") from exc

        if (
            len(feedback) != WORD_LENGTH
            or any(state not in FEEDBACK_STATES for state in feedback)
        ):
            raise ValueError(
                "feedback must contain exactly five valid feedback states"
            )
        object.__setattr__(self, "feedback", feedback)


def load_words(path: str | Path | None = None) -> tuple[str, ...]:
    """Load unique candidate answers, preserving first-seen file order.

    The bundled ``possible_words.txt`` contains the common answer pool.  A
    caller can still pass ``valid_words.txt`` (or another file) explicitly
    when it needs the broader accepted-guess dictionary.
    """

    word_path = Path(path) if path is not None else Path(__file__).with_name(
        "possible_words.txt"
    )
    words: list[str] = []
    seen: set[str] = set()

    with word_path.open("r", encoding="utf-8") as word_file:
        for line in word_file:
            value = line.strip()
            try:
                word = normalize_guess(value)
            except ValueError:
                continue
            if word not in seen:
                seen.add(word)
                words.append(word)

    if not words:
        raise ValueError(f"word list contains no valid five-letter words: {word_path}")
    return tuple(words)


def evaluate_guess(answer: str, guess: str) -> tuple[str, ...]:
    """Return canonical Wordle feedback, including duplicate-letter handling."""

    answer = normalize_guess(answer)
    guess = normalize_guess(guess)
    feedback = [ABSENT] * WORD_LENGTH
    unmatched = Counter()

    # Exact matches consume their answer positions before misplaced letters.
    for index, (answer_letter, guess_letter) in enumerate(zip(answer, guess)):
        if answer_letter == guess_letter:
            feedback[index] = CORRECT
        else:
            unmatched[answer_letter] += 1

    for index, guess_letter in enumerate(guess):
        if feedback[index] == CORRECT:
            continue
        if unmatched[guess_letter] > 0:
            feedback[index] = PRESENT
            unmatched[guess_letter] -= 1

    return tuple(feedback)


def filter_candidates(
    words: Iterable[str], attempts: Iterable[Attempt]
) -> tuple[str, ...]:
    """Keep candidates that reproduce all of the supplied observed feedback."""

    observed = tuple(attempts)
    if any(not isinstance(attempt, Attempt) for attempt in observed):
        raise ValueError("attempts must contain Attempt instances")

    candidates: list[str] = []
    for value in words:
        candidate = normalize_guess(value)
        if all(
            evaluate_guess(candidate, attempt.guess) == attempt.feedback
            for attempt in observed
        ):
            candidates.append(candidate)
    return tuple(candidates)


def count_letters(words: Iterable[str]) -> Counter[str]:
    """Count per-word letter thresholds used by the original scoring scheme."""

    counts: Counter[str] = Counter()
    for value in words:
        letter_counts = Counter(normalize_guess(value))
        for letter, amount in letter_counts.items():
            counts[letter] += 1
            for threshold in range(2, amount + 1):
                counts[f"{letter}{threshold}"] += 1
    return counts


def score_word(word: str, letter_data: Mapping[str, int]) -> int:
    """Score a word from the supplied per-letter threshold counts."""

    letter_counts = Counter(normalize_guess(word))
    score = 0
    for letter, amount in letter_counts.items():
        score += letter_data.get(letter, 0)
        for threshold in range(2, amount + 1):
            score += letter_data.get(f"{letter}{threshold}", 0)
    return score


def rank_words(words: Iterable[str], limit: int = 5) -> tuple[tuple[str, int], ...]:
    """Rank by descending score, then alphabetically to break score ties."""

    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 0:
        raise ValueError("limit must be a non-negative integer")

    normalized = tuple(normalize_guess(word) for word in words)
    letter_data = count_letters(normalized)
    scored = [(word, score_word(word, letter_data)) for word in normalized]
    scored.sort(key=lambda item: (-item[1], item[0]))
    return tuple(scored[:limit])


class WordleSession:
    """In-memory state for one game-solving session."""

    def __init__(
        self,
        words: Iterable[str],
        fallback_words: Iterable[str] | None = None,
    ) -> None:
        unique_words: list[str] = []
        seen: set[str] = set()
        for value in words:
            word = normalize_guess(value)
            if word not in seen:
                seen.add(word)
                unique_words.append(word)
        if not unique_words:
            raise ValueError("words must contain at least one valid word")

        self._all_words = tuple(unique_words)
        fallback: list[str] = []
        fallback_seen = set(self._all_words)
        for value in () if fallback_words is None else fallback_words:
            word = normalize_guess(value)
            if word not in fallback_seen:
                fallback_seen.add(word)
                fallback.append(word)
        self._fallback_words = tuple(fallback)
        self._remaining_words = self._all_words
        self._attempts: list[Attempt] = []
        self._using_fallback = False

    @property
    def all_words(self) -> tuple[str, ...]:
        return self._all_words

    @property
    def remaining_words(self) -> tuple[str, ...]:
        return self._remaining_words

    @property
    def attempts(self) -> tuple[Attempt, ...]:
        return tuple(self._attempts)

    @property
    def candidate_count(self) -> int:
        return len(self._remaining_words)

    @property
    def using_fallback(self) -> bool:
        """Whether candidates come from the broader accepted-word corpus."""

        return self._using_fallback

    @property
    def attempt_number(self) -> int:
        """Return the next 1-based board row, capped at ``MAX_ATTEMPTS``."""

        return min(len(self._attempts) + 1, MAX_ATTEMPTS)

    @property
    def solved(self) -> bool:
        return bool(self._attempts) and all(
            state == CORRECT for state in self._attempts[-1].feedback
        )

    @property
    def exhausted(self) -> bool:
        return len(self._attempts) >= MAX_ATTEMPTS and not self.solved

    @property
    def is_over(self) -> bool:
        return self.solved or self.exhausted

    def submit(self, guess: str, feedback: Sequence[str]) -> Attempt:
        """Record feedback and narrow the remaining candidates."""

        if self.is_over:
            raise RuntimeError("the session is already over")
        attempt = Attempt(guess, tuple(feedback))
        self._attempts.append(attempt)
        self._remaining_words = filter_candidates(
            self._remaining_words, (attempt,)
        )
        if not self._remaining_words and not self._using_fallback:
            expanded = filter_candidates(self._fallback_words, self._attempts)
            if expanded:
                self._remaining_words = expanded
                self._using_fallback = True
        return attempt

    def undo(self) -> Attempt | None:
        """Remove the latest attempt and recompute candidates from all words."""

        if not self._attempts:
            return None
        attempt = self._attempts.pop()
        self._recompute_candidates()
        return attempt

    def reset(self) -> None:
        """Restore the session to its initial state."""

        self._attempts.clear()
        self._remaining_words = self._all_words
        self._using_fallback = False

    def suggestions(self, limit: int = 5) -> tuple[tuple[str, int], ...]:
        return rank_words(self._remaining_words, limit)

    def _recompute_candidates(self) -> None:
        """Rebuild candidates, expanding only when the common pool is empty."""

        common = filter_candidates(self._all_words, self._attempts)
        if common or not self._fallback_words:
            self._remaining_words = common
            self._using_fallback = False
            return
        self._remaining_words = filter_candidates(
            self._fallback_words, self._attempts
        )
        self._using_fallback = bool(self._remaining_words)
