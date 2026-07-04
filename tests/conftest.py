from unittest.mock import MagicMock


def make_question(id_: str, tags: list[str] | None = None, *, answers: list | None = None) -> MagicMock:
    """Build a lightweight mock for a ChoiceQuestion.

    Args:
        id_: The question ID.
        tags: Optional list of tags. Defaults to an empty list.
        answers: Keyword-only. Optional list of answer mocks. Only set on the
            mock when provided.
    """
    question = MagicMock()
    question.id_ = id_
    question.tags = tags or []
    if answers is not None:
        question.answers = answers
    return question
