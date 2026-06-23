from collections import Counter
from pathlib import Path
from pydantic import ValidationError

from quizzer.models.questions import ChoiceQuestion
from quizzer.core.paths import DATA_PATH


class QuestionPool:
    """A collection of questions that can be used to generate quizzes."""
    def __init__(self, questions: list[ChoiceQuestion], question_paths: list[Path] | None = None):
        self.questions = questions
        self.question_paths = question_paths or []

    @classmethod
    def from_files(cls, data_path: Path) -> "QuestionPool":
        """Load questions from JSON files and return a QuestionPool"""
        questions, paths = cls.load_questions(data_path)
        return cls(questions, paths)

    @staticmethod
    def load_questions(data_path: Path) -> tuple[list[ChoiceQuestion], list[Path]]:
        """Load questions from JSON files"""
        questions = []
        paths = []
        for path in (data_path / "questions").glob("*.json"):
            print(f"Loading questions from {path}")
            with open(path) as file:
                try:
                    question = ChoiceQuestion.model_validate_json(file.read())
                except ValidationError as e:
                    print(f"Error validating question in {path}: {e}")
                    continue
            questions.append(question)
            paths.append(path)

        return questions, paths

    def get_question_path_by_id(self, question_id: str) -> Path:
        """Return the file path of a question given its ID"""
        if self.question_paths is None:
            raise ValueError("Question paths are not available in this QuestionPool")
        paths = [
            path for question, path in zip(self.questions, self.question_paths, strict=True)
            if question.id_ == question_id
        ]
        if not paths or len(paths) > 1:
            raise ValueError(f"Got paths {paths} for question with ID {question_id}")
        return paths[0]

    def get_question_by_id(self, question_id: str) -> ChoiceQuestion:
        """Return a question given its ID"""
        q = [q for q in self.questions if q.id_ == question_id]
        if not q or len(q) > 1:
            raise ValueError(f"Got questions {q} for ID {question_id}")
        return q[0]

    def __contains__(self, item: str | ChoiceQuestion) -> bool:
        """Check if a question with the given ID exists in the pool"""
        if isinstance(item, ChoiceQuestion):
            return any(q.id_ == item.id_ for q in self.questions)
        return any(q.id_ == item for q in self.questions)

    def get_tag_counts(self) -> dict[str, int]:
        """Return a sorted dict mapping each tag to its question count."""
        tag_counts = Counter()
        for q in self.questions:
            tag_counts.update(q.tags)
        return dict(sorted(tag_counts.items()))


POOL = QuestionPool.from_files(DATA_PATH)
