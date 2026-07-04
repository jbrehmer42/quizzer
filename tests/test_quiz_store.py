import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from quizzer.core.quiz_store import QuizStore
from quizzer.models.quiz import QuestionOutcome


def _make_path_mock(json_data: dict) -> MagicMock:
    """Helper to return a Path mock whose exists() is True and read_text()
    returns *json_data*.
    """
    mock_path = MagicMock(spec=Path)
    mock_path.exists.return_value = True
    mock_path.read_text.return_value = json.dumps(json_data)
    return mock_path


class TestFromFile:
    """Tests for QuizStore.from_file – only the path.exists() == True branch."""

    @pytest.fixture
    def empty_path(self) -> MagicMock:
        return _make_path_mock({"quizzes": [], "question_histories": []})

    @pytest.fixture
    def populated_path(self) -> MagicMock:
        return _make_path_mock(
            {
                "quizzes": [
                    {
                        "id": "quiz-1",
                        "name": "My Quiz",
                        "question_ids": ["q-1", "q-2"],
                        "result": None,
                        "created_at": "2026-01-01T00:00:00",
                    }
                ],
                "question_histories": [
                    {
                        "question_id": "q-1",
                        "attempts": 5,
                        "correct_answers": 3,
                    }
                ],
            }
        )

    def test_empty_json_yields_no_quizzes(self, empty_path: MagicMock) -> None:
        store = QuizStore.from_file(empty_path)
        assert store.quizzes == []

    def test_empty_json_yields_no_histories(self, empty_path: MagicMock) -> None:
        store = QuizStore.from_file(empty_path)
        assert store.question_histories == []

    def test_loads_quiz_id_and_name(self, populated_path: MagicMock) -> None:
        store = QuizStore.from_file(populated_path)
        assert len(store.quizzes) == 1
        quiz = store.quizzes[0]
        assert quiz.id == "quiz-1"
        assert quiz.name == "My Quiz"

    def test_loaded_quiz_accessible_via_get(self, populated_path: MagicMock) -> None:
        store = QuizStore.from_file(populated_path)
        assert store.get("quiz-1") is not None

    def test_loads_question_history_fields(self, populated_path: MagicMock) -> None:
        store = QuizStore.from_file(populated_path)
        history = store.get_question_history("q-1")
        assert history is not None
        assert history.attempts == 5
        assert history.correct_answers == 3


class TestRecordQuestionAttempt:
    """Tests for QuizStore.record_question_attempt."""

    @pytest.fixture
    def store(self) -> QuizStore:
        """Build a QuizStore directly, bypassing the filesystem entirely."""
        mock_path = MagicMock(spec=Path)
        return QuizStore(
            quizzes={},
            question_histories={},
            path=mock_path,
        )

    def test_unanswered_does_not_create_history(self, store: QuizStore) -> None:
        store.record_question_attempt("q-1", QuestionOutcome.UNANSWERED)
        assert store.get_question_history("q-1") is None

    @pytest.mark.parametrize(
        "outcome", [QuestionOutcome.CORRECT, QuestionOutcome.WRONG]
    )
    def test_answered_creates_history_entry(
        self, store: QuizStore, outcome: QuestionOutcome
    ) -> None:
        store.record_question_attempt("q-1", outcome)
        assert store.get_question_history("q-1") is not None

    @pytest.mark.parametrize(
        "outcome", [QuestionOutcome.CORRECT, QuestionOutcome.WRONG]
    )
    def test_first_attempt_sets_attempts_to_one(
        self, store: QuizStore, outcome: QuestionOutcome
    ) -> None:
        store.record_question_attempt("q-1", outcome)
        assert store.get_question_history("q-1").attempts == 1

    def test_subsequent_attempts_accumulate(self, store: QuizStore) -> None:
        store.record_question_attempt("q-1", QuestionOutcome.CORRECT)
        store.record_question_attempt("q-1", QuestionOutcome.WRONG)
        store.record_question_attempt("q-1", QuestionOutcome.CORRECT)
        assert store.get_question_history("q-1").attempts == 3

    def test_correct_increments_correct_answers(self, store: QuizStore) -> None:
        store.record_question_attempt("q-1", QuestionOutcome.CORRECT)
        assert store.get_question_history("q-1").correct_answers == 1

    def test_wrong_does_not_increment_correct_answers(self, store: QuizStore) -> None:
        store.record_question_attempt("q-1", QuestionOutcome.WRONG)
        assert store.get_question_history("q-1").correct_answers == 0

    def test_mixed_outcomes_tally_correctly(self, store: QuizStore) -> None:
        store.record_question_attempt("q-1", QuestionOutcome.CORRECT)
        store.record_question_attempt("q-1", QuestionOutcome.WRONG)
        store.record_question_attempt("q-1", QuestionOutcome.CORRECT)
        history = store.get_question_history("q-1")
        assert history.attempts == 3
        assert history.correct_answers == 2
