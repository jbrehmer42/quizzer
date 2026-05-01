import os
import uuid

from flask import Flask
from flask import redirect, render_template, request, session, url_for

from quizzer.core.question_pool import POOL
from quizzer.models.quiz import QuizSession, QuestionStatus, QuestionOutcome
from quizzer.models.settings import Settings
from quizzer.ui.helpers import (
    handle_question_submission,
    set_quiz_deadline,
    get_seconds_remaining,
)


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

_active_quizzes: dict[str, QuizSession] = {}
_completed_quizzes: dict[str, QuizSession] = {}
_settings = Settings()


@app.route("/")
def home():
    return render_template("index.html", questions=POOL.questions)


@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        _settings.apply_form(request.form.to_dict())
        return redirect(url_for("home"))
    return render_template("settings.html", settings=_settings)


@app.route("/quiz/start", methods=["POST"])
def start_quiz():
    selected_ids = set(request.form.getlist("question_ids"))
    selected_questions = [q for q in POOL.questions if q.id_ in selected_ids]

    if not selected_questions:
        return redirect(url_for("home"))

    old_completed_id = session.pop("completed_quiz_id", None)
    if old_completed_id:
        _completed_quizzes.pop(old_completed_id, None)

    quiz_session = QuizSession.from_settings(selected_questions, settings=_settings)
    quiz_id = str(uuid.uuid4())
    _active_quizzes[quiz_id] = quiz_session
    session["quiz_id"] = quiz_id
    session["practice_mode"] = request.form.get("mode") == "practice"

    set_quiz_deadline(request, len(selected_questions))

    return redirect(url_for("quiz_question", index=0))


@app.route("/quiz/<int:index>", methods=["GET", "POST"])
def quiz_question(index):
    """Show the quiz question at the given index, or handle answer submission if POST."""
    quiz_id = session.get("quiz_id")
    quiz_session = _active_quizzes.get(quiz_id) if quiz_id else None

    if not quiz_session:
        return redirect(url_for("home"))

    if index < 0 or index >= quiz_session.total_questions:
        return redirect(url_for("quiz_question", index=0))

    seconds_remaining = get_seconds_remaining()
    if seconds_remaining == 0 and request.method == "GET":
        return redirect(url_for("quiz_confirm"))

    if request.method == "POST":
        return handle_question_submission(quiz_session, index, request)

    return render_template(
        "quiz.html",
        question=quiz_session.get_question_by_index(index),
        index=index,
        total=quiz_session.total_questions,
        selected_answers=quiz_session.selected_answers_for(index),
        is_flagged=quiz_session.is_question_flagged(index),
        seconds_remaining=seconds_remaining,
        practice_mode=session.get("practice_mode", False),
    )


@app.route("/quiz/confirm", methods=["GET", "POST"])
def quiz_confirm():
    """Confirm quiz submission and show results on POST."""
    quiz_id = session.get("quiz_id")
    quiz_session = _active_quizzes.get(quiz_id) if quiz_id else None

    if not quiz_session or not quiz_id:
        return redirect(url_for("home"))

    if request.method == "POST":
        _completed_quizzes[quiz_id] = quiz_session
        session["completed_quiz_id"] = quiz_id
        session.pop("quiz_id", None)
        session.pop("quiz_deadline", None)
        session.pop("practice_mode", None)
        _active_quizzes.pop(quiz_id, None)
        return redirect(url_for("quiz_results"))

    total = quiz_session.total_questions
    return render_template(
        "quiz_confirm.html",
        quiz_session=quiz_session,
        last_index=total - 1,
        n_answered=quiz_session.status_counts[QuestionStatus.ANSWERED],
        n_skipped=quiz_session.status_counts[QuestionStatus.SKIPPED],
        total=total,
    )


@app.route("/quiz/results")
def quiz_results():
    """Show the results of the most recently completed quiz."""
    quiz_id = session.get("completed_quiz_id")
    quiz_session = _completed_quizzes.get(quiz_id) if quiz_id else None

    if not quiz_session:
        return redirect(url_for("home"))

    outcomes = quiz_session.score()
    total = quiz_session.total_questions
    correct = sum(1 for out in outcomes if out == QuestionOutcome.CORRECT)
    answered = sum(1 for out in outcomes if out != QuestionOutcome.UNANSWERED)

    question_outcomes = [
        {
            "index": i,
            "text": question.question,
            "outcome": outcome.value,
            "is_flagged": quiz_session.is_question_flagged(i),
        }
        for i, (question, outcome) in enumerate(zip(quiz_session.questions, outcomes, strict=True))
    ]

    return render_template(
        "quiz_results.html",
        correct=correct,
        answered=answered,
        total=total,
        skipped=total - answered,
        question_outcomes=question_outcomes,
    )


@app.route("/quiz/review/<int:index>")
def quiz_review(index):
    """Show a read-only review of the answer for the question at the given index."""
    practice_mode = session.get("practice_mode", False)

    if practice_mode:
        quiz_id = session.get("quiz_id")
        quiz_session = _active_quizzes.get(quiz_id) if quiz_id else None
    else:
        quiz_id = session.get("completed_quiz_id")
        quiz_session = _completed_quizzes.get(quiz_id) if quiz_id else None

    if not quiz_session:
        return redirect(url_for("home"))

    if index < 0 or index >= quiz_session.total_questions:
        return redirect(url_for("quiz_review", index=0))

    return render_template(
        "quiz_review.html",
        question=quiz_session.get_question_by_index(index),
        index=index,
        total=quiz_session.total_questions,
        selected_answers=quiz_session.selected_answers_for(index),
        is_flagged=quiz_session.is_question_flagged(index),
        practice_mode=practice_mode,
    )
