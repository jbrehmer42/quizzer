from pathlib import Path
from unittest.mock import MagicMock

import pytest

from quizzer.core.question_pool import QuestionPool

from conftest import make_question


class TestUpdateQuestion:
    """Tests for QuestionPool.update_question."""

    @pytest.fixture
    def updated_question(self) -> MagicMock:
        updated = make_question("id-1")
        updated.model_dump_json.return_value = '{"id_": "id-1"}'
        return updated

    @pytest.fixture
    def pool(self, updated_question: MagicMock) -> QuestionPool:
        original = make_question("id-1")
        other = make_question("id-2")
        return QuestionPool(questions=[original, other])

    def test_persists_to_resolved_path(
        self, pool: QuestionPool, updated_question: MagicMock
    ) -> None:
        fake_path = MagicMock(spec=Path)
        pool.get_question_path_by_id = MagicMock(return_value=fake_path)

        pool.update_question(updated_question)

        pool.get_question_path_by_id.assert_called_once_with("id-1")
        fake_path.write_text.assert_called_once_with('{"id_": "id-1"}\n')

    def test_replaces_question_in_memory(
        self, pool: QuestionPool, updated_question: MagicMock
    ) -> None:
        pool.get_question_path_by_id = MagicMock(return_value=MagicMock(spec=Path))

        pool.update_question(updated_question)

        assert pool.questions[0] is updated_question


class TestGetTagCounts:
    """Tests for QuestionPool.get_tag_counts."""

    def test_empty_pool_returns_empty_dict(self) -> None:
        pool = QuestionPool(questions=[])
        assert pool.get_tag_counts() == {}

    def test_counts_tags_across_questions(self) -> None:
        pool = QuestionPool(
            questions=[
                make_question("id-1", tags=["python", "testing"]),
                make_question("id-2", tags=["python"]),
            ]
        )
        assert pool.get_tag_counts() == {"python": 2, "testing": 1}

    def test_result_is_sorted_by_tag(self) -> None:
        pool = QuestionPool(
            questions=[
                make_question("id-1", tags=["zebra", "apple"]),
                make_question("id-2", tags=["mango"]),
            ]
        )
        assert list(pool.get_tag_counts().keys()) == ["apple", "mango", "zebra"]
