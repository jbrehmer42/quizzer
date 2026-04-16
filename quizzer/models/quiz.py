from enum import Enum
from dataclasses import dataclass
from collections import Counter


from quizzer.models.questions import ChoiceQuestion


class QuestionStatus(Enum):
    """Possible question status during the quiz session"""

    UNANSWERED = "unanswered"
    ANSWERED = "answered"
    SKIPPED = "skipped"


class QuestionOutcome(Enum):
    """Possible question outcomes after the quiz session is completed"""

    CORRECT = "correct"
    WRONG = "wrong"
    UNANSWERED = "unanswered"


class QuizSession:
    """A quiz session over a fixed list of questions."""

    def __init__(self, questions: list[ChoiceQuestion]):
        if not questions:
            raise ValueError("A quiz must have at least one question.")
        self.questions = questions
        self.question_status: dict[str, QuestionStatus] = {
            question.id_ : QuestionStatus.UNANSWERED for question in questions
        }
        self._selected_answers: dict[str, list[int]] = {}

    @property
    def total_questions(self) -> int:
        """Return the total number of questions in this quiz."""
        return len(self.questions)
    
    @property
    def status_counts(self) -> dict[QuestionStatus, int]:
        """Return a dict mapping each QuestionStatus to the number of questions in that status."""
        return Counter(self.question_status.values())

    def get_question_by_index(self, index: int) -> ChoiceQuestion:
        """Return the question at the given index."""
        if index < 0 or index >= len(self.questions):
            raise IndexError(f"Question index {index} is out of range.")
        return self.questions[index]
    
    def get_question_status_by_index(self, index: int) -> QuestionStatus:
        """Return the question status for the question at the given index."""
        question = self.get_question_by_index(index)
        return self.question_status[question.id_]

    def skip_question(self, index: int) -> None:
        """Mark the question at the given index as skipped."""
        question = self.questions[index]
        self.question_status[question.id_] = QuestionStatus.SKIPPED

    def answer_question(self, index: int, selected_indices: list[int]) -> None:
        """Record selected answer indices for the question at the given index."""
        question = self.questions[index]
        self._selected_answers[question.id_] = selected_indices
        self.question_status[question.id_] = QuestionStatus.ANSWERED

    def selected_answers_for(self, index: int) -> list[int]:
        """Return the previously selected answer indices for the question at the given index."""
        question = self.questions[index]
        return self._selected_answers.get(question.id_, [])

    def score(self) -> list[QuestionOutcome]:
        """Return (number_correct, number_answered) excluding skipped questions."""
        result = []
        for question in self.questions:
            status = self.question_status[question.id_]
            if status == QuestionStatus.UNANSWERED or status == QuestionStatus.SKIPPED:
                result.append(QuestionOutcome.UNANSWERED)
            else:
                selected =  [question.answers[i].text for i in self._selected_answers[question.id_]]
                correct = [answer.text for answer in question.answers if answer.correct]
                result.append(QuestionOutcome.CORRECT if set(selected) == set(correct) else QuestionOutcome.WRONG)
        return result

        #     selected =  [question.answers[i].text for i in self._selected_answers[question.id_]]
        #     correct = [answer.text for answer in question.answers if answer.correct]
        #     sum_correct += set(selected) == set(correct)
        # return sum_correct, len(answered)
