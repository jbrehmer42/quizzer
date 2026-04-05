import os
import uuid

from flask import Flask, redirect, render_template, request, session, url_for

from quizzer.core.question_pool import POOL
from quizzer.models.quiz import QuizSession


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

_active_quizzes: dict[str, QuizSession] = {}


@app.route("/")
def home():
    return render_template("index.html", questions=POOL.questions)


@app.route("/quiz/start", methods=["POST"])
def start_quiz():
    selected_ids = set(request.form.getlist("question_ids"))
    selected_questions = [q for q in POOL.questions if q.id_ in selected_ids]

    if not selected_questions:
        return redirect(url_for("home"))

    quiz_session = QuizSession(selected_questions)
    quiz_id = str(uuid.uuid4())
    _active_quizzes[quiz_id] = quiz_session
    session["quiz_id"] = quiz_id

    return redirect(url_for("quiz_page"))


@app.route("/quiz")
def quiz_page():
    quiz_id = session.get("quiz_id")
    quiz_session = _active_quizzes.get(quiz_id) if quiz_id else None
    return render_template("quiz.html", quiz_session=quiz_session)

