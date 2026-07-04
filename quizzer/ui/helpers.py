import time
import uuid

from typing import Any
from flask import Request, session, url_for, redirect
from werkzeug.wrappers import Response
from werkzeug.datastructures import MultiDict

from quizzer.models.questions import ChoiceQuestion, ChoiceAnswer
from quizzer.models.quiz import QuizSession, QuestionStatus
from quizzer.core.quiz_store import QUIZ_STORE, SavedQuiz
from quizzer.ui.state import STATE


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

    Also records the outcome of each answered question in the per-question
    history so users can track which questions they struggle with.
    """
    result = quiz_session.score()
    saved_quiz = QUIZ_STORE.get(quiz_id)
    if saved_quiz:
        saved_quiz.result = result
    else:
        saved_quiz = SavedQuiz(
            id=quiz_id,
            name=f"Quiz ({result.total} questions)",
            question_ids=[q.id_ for q in quiz_session.questions],
            result=result,
        )

    for question, outcome in zip(quiz_session.questions, result.outcomes, strict=True):
        QUIZ_STORE.record_question_attempt(question.id_, outcome)

    QUIZ_STORE.save_quiz(saved_quiz)


def parse_question_form(form: MultiDict, question: ChoiceQuestion) -> dict[str, Any]:
    """Build a question data dict from the edit form, preserving non-editable fields.

    Answer correctness is taken from the original question and never from the form,
    so editing can never change which answers are correct.
    """
    answers: list[ChoiceAnswer] = []
    i = 0
    while f"answer_text_{i}" in form:
        answers.append(ChoiceAnswer(
            text=form[f"answer_text_{i}"],
            correct=question.answers[i].correct,
            rationale=form.get(f"answer_rationale_{i}", ""),
        ))
        i += 1

    data = question.model_dump()
    data.update(
        question=form.get("question_text", ""),
        answers=answers,
        tags=[t.strip() for t in form.get("tags", "").split(",") if t.strip()],
        resources=[r.strip() for r in form.get("resources", "").splitlines() if r.strip()],
        explanation=form.get("explanation", ""),
    )
    return data


def question_data_to_form_data(data: dict) -> dict[str, str]:
    """Convert a question data dict into the structure expected by the edit template."""
    return {
        "question_text": data["question"],
        "answers": data["answers"],
        "tags": ", ".join(data["tags"]),
        "explanation": data["explanation"],
        "resources": "\n".join(data["resources"]),
    }


def prepare_quiz_session(
    questions: list[ChoiceQuestion],
    quiz_id: str | None = None,
    practice_mode: bool = False,
) -> None:
    """Prepare a new quiz session with the given questions and store its properties
    in the session.
    """
    old_completed_id = session.pop("completed_quiz_id", None)
    if old_completed_id:
        STATE.delete(old_completed_id)

    quiz_session = QuizSession.from_settings(questions, settings=STATE.settings)
    quiz_id = str(uuid.uuid4()) if quiz_id is None else quiz_id
    STATE.put(quiz_id, quiz_session)
    session["quiz_id"] = quiz_id
    session["practice_mode"] = practice_mode    
