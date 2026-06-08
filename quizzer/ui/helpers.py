import time

from flask import Request, session, url_for, redirect
from werkzeug.wrappers import Response

from quizzer.models.quiz import QuizSession, QuestionStatus, ScoringResult
from quizzer.core.quiz_store import QUIZ_STORE, SavedQuiz


def _record_answer(quiz_session: QuizSession, index: int, req: Request) -> None:
    """Record the user's answer selection for the question at the given index."""
    selected_indices = [int(i) for i in req.form.getlist("answer_indices")]
    if selected_indices:
        quiz_session.answer_question(index, selected_indices)
    elif quiz_session.get_question_status_by_index(index) == QuestionStatus.UNANSWERED:
        quiz_session.skip_question(index)


def _get_navigation_target(index: int, req: Request) -> str:
    """Determine the redirect URL based on which navigation button was pressed."""
    if "show_solution_button" in req.form:
        return url_for("quiz_review", index=index)
    if "previous_button" in req.form:
        return url_for("quiz_question", index=index - 1)
    if "next_button" in req.form:
        return url_for("quiz_question", index=index + 1)
    # finish_button or fallback
    return url_for("quiz_confirm")


def handle_question_submission(quiz_session: QuizSession, index: int, req: Request) -> Response:
    """Handle form submission for a quiz question, updating the quiz session accordingly."""
    if "bookmark_button" in req.form:
        selected_indices = [int(i) for i in req.form.getlist("answer_indices")]
        if selected_indices:
            quiz_session.answer_question(index, selected_indices)
        quiz_session.flag_question(index)
        return redirect(url_for("quiz_question", index=index))

    _record_answer(quiz_session, index, req)
    return redirect(_get_navigation_target(index, req))


def set_quiz_deadline(req: Request, n_questions: int) -> None:
    """Set a quiz deadline in the session if the timer is enabled, based on the
    number of questions and minutes per question.
    """
    session.pop("quiz_deadline", None)
    if req.form.get("enable_timer") == "1":
        try:
            minutes_per_question = float(req.form.get("minutes_per_question", 4))
        except ValueError:
            minutes_per_question = 4.0
        if minutes_per_question > 0:
            session["quiz_deadline"] = time.time() + n_questions * minutes_per_question * 60


def get_seconds_remaining() -> int | None:
    """Get the number of seconds remaining until the quiz deadline, or None if no
    deadline is set.
    """
    deadline = session.get("quiz_deadline")
    return max(0, int(deadline - time.time())) if deadline is not None else None


def persist_quiz(quiz_session: QuizSession, quiz_id: str) -> None:
    """Persist the quiz and its result in the quiz store, either by updating
    an existing saved quiz or by creating a new one if no saved quiz exists
    for the current quiz session.
    """
    saved_quiz_id = session.pop("saved_quiz_id", None) or quiz_id
    result = quiz_session.score()

    saved_quiz = QUIZ_STORE.get(saved_quiz_id)
    if saved_quiz:
        saved_quiz.result = result
    else:
        saved_quiz = SavedQuiz(
            id=saved_quiz_id,
            name=f"Quiz ({result.total} questions)",
            question_ids=[q.id_ for q in quiz_session.questions],
            result=result,
        )
    QUIZ_STORE.save_quiz(saved_quiz)
