import json
from datetime import datetime
from pathlib import Path
from typing import Final

from pydantic import BaseModel, Field

from quizzer.core.paths import PERSISTENCE_PATH
from quizzer.models.quiz import ScoringResult, QuestionOutcome


class SavedQuiz(BaseModel):
    """A saved quiz definition with optional result from last attempt."""

    id: str
    name: str
    question_ids: list[str]
    result: ScoringResult | None = None
    created_at: datetime = Field(default_factory=datetime.now)


class SavedQuestionHistory(BaseModel):
    """A saved question history which tracks the number of attempts and
    correct answers for a specific question.
    """

    question_id: str
    attempts: int = 0
    correct_answers: int = 0


class QuizStore:
    """Manages persistence of saved quizzes to a local JSON file."""

    def __init__(
        self,
        quizzes: dict[str, SavedQuiz],
        question_histories: dict[str, SavedQuestionHistory],
        path: Path = PERSISTENCE_PATH
    ):
        self._path = path
        self._quizzes: dict[str, SavedQuiz] = quizzes
        self._question_histories: dict[str, SavedQuestionHistory] = question_histories

    @classmethod
    def from_file(cls, path: Path = PERSISTENCE_PATH) -> "QuizStore":
        """Factory method to create a QuizStore instance from the default file."""
        if not path.exists():
            print(f"Quiz store file not found: {path}.")
            answer = input("Create new quiz store in this location? (y/n) ")
            if answer.casefold().startswith("y"):
                return cls(quizzes={}, question_histories={}, path=path)
            else:
                raise RuntimeError(
                    f"Quiz store file not found: {path} and no confirmation to create new one."
                )

        data = json.loads(path.read_text())

        quizzes = {}
        for item in data["quizzes"]:
            quiz = SavedQuiz.model_validate(item)
            quizzes[quiz.id] = quiz

        question_histories = {}
        for item in data["question_histories"]:
            history = SavedQuestionHistory.model_validate(item)
            question_histories[history.question_id] = history

        return cls(quizzes=quizzes, question_histories=question_histories, path=path)

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "quizzes": [quiz.model_dump(mode="json") for quiz in self._quizzes.values()],
            "question_histories": [
                history.model_dump(mode="json")
                for history in self._question_histories.values()
            ],
        }
        self._path.write_text(json.dumps(data, indent=2, default=str) + "\n")

    @property
    def quizzes(self) -> list[SavedQuiz]:
        return list(self._quizzes.values())

    @property
    def question_histories(self) -> list[SavedQuestionHistory]:
        return list(self._question_histories.values())

    def get(self, quiz_id: str) -> SavedQuiz | None:
        return self._quizzes.get(quiz_id)

    def get_question_history(self, question_id: str) -> SavedQuestionHistory | None:
        return self._question_histories.get(question_id)

    def save_quiz(self, quiz: SavedQuiz) -> None:
        """Add or update a quiz in the store and persist to file."""
        self._quizzes[quiz.id] = quiz
        self._save()

    def record_question_attempt(self, question_id: str, outcome: QuestionOutcome) -> None:
        """Record a single attempt for a question (if the question 
        was not skipped) and update its history in memory.
        """
        if outcome == QuestionOutcome.UNANSWERED:
            return
        history = self._question_histories.get(question_id)
        if history is None:
            history = SavedQuestionHistory(question_id=question_id)
            self._question_histories[question_id] = history
        history.attempts += 1
        if outcome == QuestionOutcome.CORRECT:
            history.correct_answers += 1

    def flush(self) -> None:
        """Persist the current state of the store to file."""
        self._save()

    def delete_quiz(self, quiz_id: str) -> None:
        """Remove a quiz from the store by ID and persist changes to file."""
        self._quizzes.pop(quiz_id, None)
        self._save()


QUIZ_STORE: Final[QuizStore] = QuizStore.from_file()
