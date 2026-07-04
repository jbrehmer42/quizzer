from unittest.mock import MagicMock, patch

from quizzer.core.sampling import sample_questions_by_tags

from conftest import make_question


class TestSampleQuestionsByTags:
    """Tests for sample_questions_by_tags."""

    def test_empty_question_list_returns_empty(self) -> None:
        result = sample_questions_by_tags([], tags={"a"}, max_questions=5)
        assert result == []

    def test_max_questions_zero_returns_empty(self) -> None:
        questions = [make_question("q-1", ["a"])]
        result = sample_questions_by_tags(questions, tags={"a"}, max_questions=0)
        assert result == []

    def test_empty_tags_returns_empty(self) -> None:
        questions = [make_question("q-1", ["a"])]
        result = sample_questions_by_tags(questions, tags=set(), max_questions=5)
        assert result == []

    def test_returns_all_when_pool_smaller_than_max(self) -> None:
        questions = [
            make_question("q-1", ["a"]),
            make_question("q-2", ["b"]),
        ]
        result = sample_questions_by_tags(questions, tags={"a", "b"}, max_questions=99)
        assert len(result) == 2

    def test_only_returns_questions_matching_requested_tags(self) -> None:
        relevant = make_question("q-1", ["a"])
        irrelevant = make_question("q-2", ["z"])
        result = sample_questions_by_tags(
            [relevant, irrelevant], tags={"a"}, max_questions=5
        )
        assert irrelevant not in result

    def test_question_without_any_requested_tag_never_selected(self) -> None:
        questions = [make_question("q-1", ["x"]), make_question("q-2", ["y"])]
        result = sample_questions_by_tags(questions, tags={"a", "b"}, max_questions=5)
        assert result == []

    def test_no_duplicate_questions_single_tag(self) -> None:
        questions = [make_question(f"q-{i}", ["a"]) for i in range(5)]
        result = sample_questions_by_tags(questions, tags={"a"}, max_questions=5)
        ids = [q.id_ for q in result]
        assert len(ids) == len(set(ids))

    def test_multi_tag_question_not_duplicated(self) -> None:
        """A question belonging to both requested tags must appear at most once."""
        shared = make_question("shared", ["a", "b"])
        result = sample_questions_by_tags(
            [shared], tags={"a", "b"}, max_questions=5
        )
        assert result.count(shared) <= 1

    @patch("quizzer.core.sampling.random.choice", side_effect=lambda seq: seq[0])
    def test_each_present_tag_gets_at_least_one_question(
        self, _mock_choice: MagicMock
    ) -> None:
        """With deterministic selection, every tag with available questions
        must be represented in the result when max_questions >= number of tags.
        """
        q_a = make_question("q-a", ["a"])
        q_b = make_question("q-b", ["b"])
        q_c = make_question("q-c", ["c"])
        result = sample_questions_by_tags(
            [q_a, q_b, q_c], tags={"a", "b", "c"}, max_questions=3
        )
        result_ids = {q.id_ for q in result}
        assert {"q-a", "q-b", "q-c"} == result_ids

    @patch("quizzer.core.sampling.random.choice", side_effect=lambda seq: seq[0])
    def test_exhausted_tag_does_not_block_remaining_tags(
        self, _mock_choice: MagicMock
    ) -> None:
        """When one tag runs out of questions the others can still fill up to max."""
        q_a = make_question("q-a", ["a"])
        q_b1 = make_question("q-b1", ["b"])
        q_b2 = make_question("q-b2", ["b"])
        result = sample_questions_by_tags(
            [q_a, q_b1, q_b2], tags={"a", "b"}, max_questions=3
        )
        assert len(result) == 3
