from enum import Enum
from dataclasses import dataclass


from quizzer.models.questions import ChoiceQuestion



class QuestionStatus(Enum):
    UNANSWERED = "unanswered"
    ANSWERED = "answered"
    SKIPPED = "skipped"



class QuizSession:
    """A quiz session over a fixed list of questions."""

    def __init__(self, questions: list[ChoiceQuestion]):
        if not questions:
            raise ValueError("A quiz must have at least one question.")
        self.questions = questions
        self.question_status: dict[str, QuestionStatus] = {question.id_ : QuestionStatus.UNANSWERED for question in questions}
        self._index: int = 0
        self._selected_answers: dict[str, list[int]] = {}

    def current_question(self) -> ChoiceQuestion | None:
        """Return the current question, or None if the quiz is finished."""
        if self.is_finished():
            return None
        return self.questions[self._index]

    def submit_answer(self, selected_indices: list[int]) -> bool:
        """Record selected answer indices for the current question and advance.

        Returns True if the selection exactly matches the correct answers.
        """
        question = self.current_question()
        if question is None:
            raise ValueError("No current question — the quiz is already finished.")
        correct_indices = {ind for ind, answer in enumerate(question.answers) if answer.correct}
        self._selected_answers[question.id_] = selected_indices
        self.question_status[question.id_] = QuestionStatus.ANSWERED
        self._index += 1
        return correct_indices == set(selected_indices)

    def skip(self) -> None:
        """Mark the current question as skipped and advance to the next one"""
        question = self.current_question()
        if question is None:
            raise ValueError("No current question — the quiz is already finished.")
        self.question_status[question.id_] = QuestionStatus.SKIPPED
        self._index += 1

    def next(self) -> None:
        """Advance to the next question without recording any answer."""
        if not self.is_finished():
            self._index += 1

    def score(self) -> tuple[int, int]:
        """Return (number_correct, number_answered) excluding skipped questions."""
        answered = [question for question in self.questions if self.question_status[question.id_] == QuestionStatus.ANSWERED]
        sum_correct = 0
        for question in answered:
            selected =  [question.answers[i].text for i in self._selected_answers[question.id_]]
            correct = [answer.text for answer in question.answers if answer.correct]
            sum_correct += set(selected) == set(correct)
        return sum_correct, len(answered)

    def is_finished(self) -> bool:
        """Return True when all questions have been answered or skipped"""
        return self._index >= len(self.questions)

    @property
    def progress(self) -> tuple[int, int]:
        """Return (current_position, total_questions)."""
        return self._index, len(self.questions)
