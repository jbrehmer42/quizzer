import os
import uuid

from flask import Flask, Request
from flask import redirect, render_template, request, session, url_for
from werkzeug.wrappers import Response

from quizzer.core.question_pool import POOL
from quizzer.models.quiz import QuizSession, QuestionStatus


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

_active_quizzes: dict[str, QuizSession] = {}
_completed_quizzes: dict[str, QuizSession] = {}



def handle_question_submission(quiz_session: QuizSession, index: int, req: Request) -> Response:
    """Handle form submission for a quiz question, updating the quiz session accordingly."""
    next_pressed = "next_button" in req.form.keys()
    prev_pressed = "previous_button" in req.form.keys()
    selected_indices = [int(i) for i in req.form.getlist("answer_indices")]
    status = quiz_session.get_question_status_by_index(index)
    if selected_indices:
        quiz_session.answer_question(index, selected_indices)
    elif status == QuestionStatus.UNANSWERED:
        quiz_session.skip_question(index)
    
    if not next_pressed and not prev_pressed:
        return redirect(url_for("quiz_confirm"))

    new_index = index - 1 if prev_pressed else index + 1
    return redirect(url_for("quiz_question", index=new_index))


@app.route("/")
def home():
    return render_template("index.html", questions=POOL.questions)


@app.route("/quiz/start", methods=["POST"])
def start_quiz():
    selected_ids = set(request.form.getlist("question_ids"))
    selected_questions = [q for q in POOL.questions if q.id_ in selected_ids]

    if not selected_questions:
        return redirect(url_for("home"))

    old_completed_id = session.pop("completed_quiz_id", None)
    if old_completed_id:
        _completed_quizzes.pop(old_completed_id, None)

    quiz_session = QuizSession(selected_questions)
    quiz_id = str(uuid.uuid4())
    _active_quizzes[quiz_id] = quiz_session
    session["quiz_id"] = quiz_id

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

    if request.method == "POST":
        return handle_question_submission(quiz_session, index, request)

    return render_template(
        "quiz.html",
        question=quiz_session.get_question_by_index(index),
        index=index,
        total=quiz_session.total_questions,
        selected_answers=quiz_session.selected_answers_for(index),
    )


@app.route("/quiz/confirm", methods=["GET", "POST"])
def quiz_confirm():
    """Confirm quiz submission and show results on POST."""
    quiz_id = session.get("quiz_id")
    quiz_session = _active_quizzes.get(quiz_id) if quiz_id else None

    if not quiz_session:
        return redirect(url_for("home"))

    if request.method == "POST":
        _completed_quizzes[quiz_id] = quiz_session
        session["completed_quiz_id"] = quiz_id
        session.pop("quiz_id", None)
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

    correct, answered = quiz_session.score()
    total = quiz_session.total_questions

    question_outcomes = [
        {"index": i, "text": question.question, "outcome": quiz_session.get_question_outcome_by_index(i).value}
        for i, question in enumerate(quiz_session.questions)
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
    )
