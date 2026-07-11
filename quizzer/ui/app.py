import os

from flask import Flask
from flask import redirect, render_template, request, session, url_for
from pydantic import ValidationError

from quizzer.core.question_pool import POOL
from quizzer.core.quiz_store import QUIZ_STORE
from quizzer.core.sampling import sample_questions_by_tags
from quizzer.models.questions import ChoiceQuestion
from quizzer.models.quiz import QuestionStatus
from quizzer.ui.state import STATE
from quizzer.ui.helpers import (
    handle_question_submission,
    set_quiz_deadline,
    get_seconds_remaining,
    persist_quiz,
    prepare_quiz_session,
    parse_question_form,
    question_data_to_form_data,
)


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")


@app.context_processor
def inject_appearance():
    return {"dark_mode": STATE.settings.appearance.dark_mode}


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/quiz/create")
def create_quiz():
    return render_template("create_quiz.html", questions=POOL.questions)


@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        STATE.settings.apply_form(request.form.to_dict())
        return redirect(url_for("home"))
    return render_template("settings.html", settings=STATE.settings)


@app.route("/quiz/start", methods=["POST"])
def start_quiz():
    selected_ids = set(request.form.getlist("question_ids"))
    selected_questions = [q for q in POOL.questions if q.id_ in selected_ids]

    if not selected_questions:
        return redirect(url_for("create_quiz"))

    practice_mode = request.form.get("mode") == "practice"
    prepare_quiz_session(
        selected_questions,
        practice_mode=practice_mode,
        quiz_name=request.form.get("quiz_name"),
    )
    set_quiz_deadline(request, len(selected_questions))
    return redirect(url_for("quiz_question", index=0))


@app.route("/quiz/by-tags", methods=["GET"])
def quiz_by_tags():
    """Show the tag-based quiz creation page."""
    return render_template("quiz_by_tags.html", tags=POOL.get_tag_counts())


@app.route("/quiz/start-by-tags", methods=["POST"])
def start_quiz_by_tags():
    """Start a quiz using randomly selected questions from the chosen tags."""
    selected_tags = set(request.form.getlist("selected_tags"))
    if not selected_tags:
        return redirect(url_for("quiz_by_tags"))

    max_questions = int(request.form.get("max_questions", 60))
    selected_questions = sample_questions_by_tags(POOL.questions, selected_tags, max_questions)

    if not selected_questions:
        return redirect(url_for("quiz_by_tags"))

    practice_mode = request.form.get("mode") == "practice"
    prepare_quiz_session(
        selected_questions,
        practice_mode=practice_mode,
        quiz_name=request.form.get("quiz_name"),
    )
    set_quiz_deadline(request, len(selected_questions))
    return redirect(url_for("quiz_question", index=0))


@app.route("/quiz/<int:index>", methods=["GET", "POST"])
def quiz_question(index):
    """Show the quiz question at the given index, or handle answer submission if POST."""
    quiz_id = session.get("quiz_id")
    quiz_session = STATE.get(quiz_id) if quiz_id else None

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
    quiz_session = STATE.get(quiz_id) if quiz_id else None

    if not quiz_session or not quiz_id:
        return redirect(url_for("home"))

    if request.method == "POST":
        session["completed_quiz_id"] = quiz_id
        session.pop("quiz_deadline", None)
        session.pop("practice_mode", None)
        persist_quiz(quiz_session, quiz_id)
        session.pop("quiz_id", None)
        session.pop("quiz_name", None)
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
    quiz_session = STATE.get(quiz_id) if quiz_id else None

    if not quiz_session:
        return redirect(url_for("home"))

    result = quiz_session.score()
    question_outcomes = [
        {
            "index": i,
            "text": question.question,
            "outcome": outcome.value,
            "is_flagged": quiz_session.is_question_flagged(i),
        }
        for i, (question, outcome) in enumerate(
            zip(quiz_session.questions, result.outcomes, strict=True)
        )
    ]

    return render_template(
        "quiz_results.html",
        correct=result.correct,
        answered=result.answered,
        total=result.total,
        skipped=result.skipped,
        question_outcomes=question_outcomes,
    )


@app.route("/quiz/review/<int:index>")
def quiz_review(index):
    """Show a read-only review of the answer for the question at the given index."""
    practice_mode = session.get("practice_mode", False)

    quiz_id = session.get("quiz_id") if practice_mode else session.get("completed_quiz_id")
    quiz_session = STATE.get(quiz_id) if quiz_id else None

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


@app.route("/edit")
def edit_list():
    """Show all questions for selection to edit."""
    return render_template("edit_list.html", questions=POOL.questions)


@app.route("/edit/<question_id>", methods=["GET", "POST"])
def edit_question(question_id: str):
    """Edit a question via individual form fields."""
    question = POOL.get_question_by_id(question_id)
    context = {
        "referrer": request.args.get("referrer", "edit_list"),
        "quiz_index": request.args.get("quiz_index", type=int),
    }

    if request.method == "POST":
        data = parse_question_form(request.form, question)
        try:
            updated = ChoiceQuestion.model_validate(data)
        except ValidationError as e:
            return render_template(
                "edit_question.html",
                question=question,
                form_data=question_data_to_form_data(data),
                error=str(e),
                **context,
            )
        POOL.update_question(updated)
        return redirect(url_for("edit_question", question_id=updated.id_))

    return render_template(
        "edit_question.html",
        question=question,
        form_data=question_data_to_form_data(question.model_dump()),
        error=None,
        **context,
    )


@app.route("/history")
def history():
    """Show all saved quizzes with their result statistics."""
    saved_quizzes = QUIZ_STORE.quizzes
    return render_template("history.html", saved_quizzes=saved_quizzes)


@app.route("/history/<quiz_id>/retake", methods=["POST"])
def retake_quiz(quiz_id: str):
    """Retake a previously saved quiz. Check whether all questions still
    exist in the pool before starting.
    """
    saved_quiz = QUIZ_STORE.get(quiz_id)
    if not saved_quiz:
        return redirect(url_for("history"))

    missing_ids = [qid for qid in saved_quiz.question_ids if qid not in POOL]
    if missing_ids:
        return render_template(
            "history.html",
            saved_quizzes=QUIZ_STORE.quizzes,
            error=(
                f"Cannot retake quiz: {len(missing_ids)} question(s) no longer exist "
                f"in the pool. Missing IDs: {', '.join(missing_ids)}",
            )
        )

    available_questions = [
        POOL.get_question_by_id(qid) for qid in saved_quiz.question_ids if qid in POOL
    ]
    practice_mode = request.form.get("mode") == "practice"
    prepare_quiz_session(available_questions, quiz_id=quiz_id, practice_mode=practice_mode)
    set_quiz_deadline(request, len(available_questions))
    return redirect(url_for("quiz_question", index=0))


@app.route("/history/<quiz_id>/delete", methods=["POST"])
def delete_saved_quiz(quiz_id: str):
    """Delete a saved quiz from history."""
    QUIZ_STORE.delete_quiz(quiz_id)
    return redirect(url_for("history"))
