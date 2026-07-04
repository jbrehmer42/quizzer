from unittest.mock import MagicMock

import pytest

from quizzer.models.quiz import QuestionOutcome, QuestionStatus, QuizSession

from conftest import make_question


def make_answer(text: str, correct: bool) -> MagicMock:
    """Lightweight stand-in for a ChoiceAnswer."""
    answer = MagicMock()
    answer.text = text
    answer.correct = correct
    return answer


class TestAnswerQuestion:
    """Tests for QuizSession.answer_question."""

    @pytest.fixture
    def session(self) -> QuizSession:
        return QuizSession([make_question("q1"), make_question("q2")])

    def test_sets_status_to_answered(self, session: QuizSession) -> None:
        session.answer_question(0, [1])

        assert session.question_status["q1"] == QuestionStatus.ANSWERED

    def test_records_selected_indices(self, session: QuizSession) -> None:
        session.answer_question(0, [0, 2])

        assert session._selected_answers["q1"] == [0, 2]

    def test_overwrites_previous_answer(self, session: QuizSession) -> None:
        session.answer_question(0, [0])
        session.answer_question(0, [1, 2])

        assert session._selected_answers["q1"] == [1, 2]


class TestAssignOutcomes:
    """Tests for QuizSession._assign_outcomes."""

    def _session_with_state(
        self,
        questions: list,
        statuses: dict[str, QuestionStatus],
        selected_answers: dict[str, list[int]] | None = None,
    ) -> QuizSession:
        """Build a QuizSession with explicit internal state
        """
        session = QuizSession(questions)
        session.question_status = statuses
        session._selected_answers = selected_answers or {}
        return session

    @pytest.mark.parametrize("status", [QuestionStatus.UNANSWERED, QuestionStatus.SKIPPED])
    def test_non_answered_question_gets_unanswered_outcome(
        self, status: QuestionStatus
    ) -> None:
        q = make_question("q1", answers=[make_answer("A", correct=True), make_answer("B", correct=False)])
        session = self._session_with_state([q], {"q1": status})

        assert session._assign_outcomes() == [QuestionOutcome.UNANSWERED]

    def test_single_correct_answer(self) -> None:
        q = make_question("q1", answers=[make_answer("A", correct=True), make_answer("B", correct=False)])
        session = self._session_with_state(
            [q],
            {"q1": QuestionStatus.ANSWERED},
            {"q1": [0]},  # index 0 → "A" (correct)
        )

        assert session._assign_outcomes() == [QuestionOutcome.CORRECT]

    def test_single_wrong_answer(self) -> None:
        q = make_question("q1", answers=[make_answer("A", correct=True), make_answer("B", correct=False)])
        session = self._session_with_state(
            [q],
            {"q1": QuestionStatus.ANSWERED},
            {"q1": [1]},  # index 1 → "B" (wrong)
        )

        assert session._assign_outcomes() == [QuestionOutcome.WRONG]

    def test_all_correct_answers_selected_for_multi_answer_question(self) -> None:
        q = make_question("q1", answers=[
            make_answer("A", correct=True),
            make_answer("B", correct=False),
            make_answer("C", correct=True),
        ])
        session = self._session_with_state(
            [q],
            {"q1": QuestionStatus.ANSWERED},
            {"q1": [0, 2]},  # both correct answers selected
        )

        assert session._assign_outcomes() == [QuestionOutcome.CORRECT]

    def test_partial_selection_of_multi_answer_question_is_wrong(self) -> None:
        q = make_question("q1", answers=[
            make_answer("A", correct=True),
            make_answer("B", correct=False),
            make_answer("C", correct=True),
        ])
        session = self._session_with_state(
            [q],
            {"q1": QuestionStatus.ANSWERED},
            {"q1": [0]},  # only one of two correct answers selected
        )

        assert session._assign_outcomes() == [QuestionOutcome.WRONG]

    def test_mixed_outcomes_across_multiple_questions(self) -> None:
        q1 = make_question("q1", answers=[make_answer("A", correct=True), make_answer("B", correct=False)])
        q2 = make_question("q2", answers=[make_answer("X", correct=True), make_answer("Y", correct=False)])
        q3 = make_question("q3", answers=[make_answer("P", correct=True), make_answer("Q", correct=False)])
        session = self._session_with_state(
            [q1, q2, q3],
            {
                "q1": QuestionStatus.ANSWERED,
                "q2": QuestionStatus.ANSWERED,
                "q3": QuestionStatus.SKIPPED,
            },
            {
                "q1": [0],  # correct
                "q2": [1],  # wrong
            },
        )

        assert session._assign_outcomes() == [
            QuestionOutcome.CORRECT,
            QuestionOutcome.WRONG,
            QuestionOutcome.UNANSWERED,
        ]

    def test_outcome_order_matches_question_order(self) -> None:
        q1 = make_question("q1", answers=[make_answer("A", correct=True)])
        q2 = make_question("q2", answers=[make_answer("B", correct=True)])
        session = self._session_with_state(
            [q1, q2],
            {"q1": QuestionStatus.SKIPPED, "q2": QuestionStatus.ANSWERED},
            {"q2": [0]},
        )
        outcomes = session._assign_outcomes()

        assert outcomes[0] == QuestionOutcome.UNANSWERED
        assert outcomes[1] == QuestionOutcome.CORRECT
