import json
from datetime import datetime
from pathlib import Path
from typing import Final

from pydantic import BaseModel, Field

from quizzer.core.paths import PERSISTENCE_PATH


class QuizResult(BaseModel):
    """Result statistics from a completed quiz attempt."""

    correct: int
    answered: int
    total: int
    completed_at: datetime = Field(default_factory=datetime.now)


class SavedQuiz(BaseModel):
    """A saved quiz definition with optional result from last attempt."""

    id: str
    name: str
    question_ids: list[str]
    result: QuizResult | None = None
    created_at: datetime = Field(default_factory=datetime.now)


class QuizStore:
    """Manages persistence of saved quizzes to a local JSON file."""

    def __init__(self, quizzes: dict[str, SavedQuiz], path: Path = PERSISTENCE_PATH):
        self._path = path
        self._quizzes: dict[str, SavedQuiz] = quizzes

    @classmethod
    def from_file(cls, path: Path = PERSISTENCE_PATH) -> "QuizStore":
        """Factory method to create a QuizStore instance from the default file."""
        if not path.exists():
            print(f"Quiz store file not found: {path}.")
            answer = input("Create new quiz store in this location? (y/n) ")
            if answer.casefold() != "y":
                return cls(quizzes={}, path=path)
            else:
                raise RuntimeError(
                    f"Quiz store file not found: {path} and no confirmation to create new one."
                )
        quizzes = {}
        data = json.loads(path.read_text())
        for item in data:
            quiz = SavedQuiz.model_validate(item)
            quizzes[quiz.id] = quiz
        return cls(quizzes=quizzes, path=path)

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = [quiz.model_dump(mode="json") for quiz in self._quizzes.values()]
        self._path.write_text(json.dumps(data, indent=2, default=str) + "\n")

    @property
    def quizzes(self) -> list[SavedQuiz]:
        return list(self._quizzes.values())

    def get(self, quiz_id: str) -> SavedQuiz | None:
        return self._quizzes.get(quiz_id)

    def save_quiz(self, quiz: SavedQuiz) -> None:
        """Add or update a quiz in the store and persist to file."""
        self._quizzes[quiz.id] = quiz
        self._save()

    def delete_quiz(self, quiz_id: str) -> None:
        """Remove a quiz from the store by ID and persist changes to file."""
        self._quizzes.pop(quiz_id, None)
        self._save()


QUIZ_STORE: Final[QuizStore] = QuizStore.from_file()
