from pathlib import Path
from pydantic import ValidationError

from quizzer.models.questions import ChoiceQuestion
from quizzer.core.paths import DATA_PATH


class QuestionPool:
    """A collection of questions that can be used to generate quizzes."""
    def __init__(self, questions: list[ChoiceQuestion]):
        self.questions = questions

    @classmethod
    def from_files(cls, data_path: Path) -> "QuestionPool":
        """Load questions from JSON files and return a QuestionPool"""
        questions = cls.load_questions(data_path)
        return cls(questions)

    @staticmethod
    def load_questions(data_path: Path) -> list[ChoiceQuestion]:
        """Load questions from JSON files"""
        out = []
        for path in (data_path / "questions").glob("*.json"):
            print(f"Loading questions from {path}")
            with open(path) as file:
                try:
                    question = ChoiceQuestion.model_validate_json(file.read())
                except ValidationError as e:
                    print(f"Error validating question in {path}: {e}")
                    continue
            out.append(question)

        return out


POOL = QuestionPool.from_files(DATA_PATH)
