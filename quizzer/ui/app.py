import json
import os
import uuid

from flask import Flask
from flask import redirect, render_template, request, session, url_for
from pydantic import ValidationError

from quizzer.core.question_pool import POOL
from quizzer.core.quiz_store import QUIZ_STORE
from quizzer.core.sampling import sample_questions_by_tags
from quizzer.models.questions import ChoiceQuestion
from quizzer.models.quiz import QuizSession, QuestionStatus
from quizzer.models.settings import Settings
from quizzer.ui.helpers import (
    handle_question_submission,
    set_quiz_deadline,
    get_seconds_remaining,
    persist_quiz,
)


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

_active_quizzes: dict[str, QuizSession] = {}
_completed_quizzes: dict[str, QuizSession] = {}
_settings = Settings()


@app.context_processor
def inject_appearance():
    return {"dark_mode": _settings.appearance.dark_mode}


def prepare_quiz_session(questions: list[ChoiceQuestion], saved_quiz_id: str | None = None) -> None:
    """Prepare a new quiz session with the given questions and store its properties
    in the session.
    """
    old_completed_id = session.pop("completed_quiz_id", None)
    if old_completed_id:
        _completed_quizzes.pop(old_completed_id, None)

    quiz_session = QuizSession.from_settings(questions, settings=_settings)
    quiz_id = str(uuid.uuid4())
    _active_quizzes[quiz_id] = quiz_session
    session["quiz_id"] = quiz_id
    if saved_quiz_id is not None:
        session["saved_quiz_id"] = saved_quiz_id
    else:
        session.pop("saved_quiz_id", None)
    session["practice_mode"] = request.form.get("mode") == "practice"
    set_quiz_deadline(request, len(questions))


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

    prepare_quiz_session(selected_questions)
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

    prepare_quiz_session(selected_questions)
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
        session.pop("quiz_deadline", None)
        session.pop("practice_mode", None)
        _active_quizzes.pop(quiz_id, None)
        persist_quiz(quiz_session, quiz_id)
        session.pop("quiz_id", None)
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


@app.route("/edit")
def edit_list():
    """Show all questions for selection to edit."""
    return render_template("edit_list.html", questions=POOL.questions)


@app.route("/edit/<question_id>", methods=["GET", "POST"])
def edit_question(question_id: str):
    """Edit a question via individual form fields."""
    question = POOL.get_question_by_id(question_id)
    if not question:
        return redirect(url_for("edit_list"))

    # Get referrer info from query parameters
    referrer = request.args.get("referrer", "edit_list")
    quiz_index = request.args.get("quiz_index", type=int)

    error = None
    form_data: dict | None = None

    if request.method == "POST":
        form = request.form

        # Reconstruct answers from indexed form fields
        answers = []
        i = 0
        while f"answer_text_{i}" in form:
            answers.append({
                "text": form[f"answer_text_{i}"],
                "correct": f"answer_correct_{i}" in form,
                "rationale": form.get(f"answer_rationale_{i}", ""),
            })
            i += 1

        # Build the full question dict, preserving non-editable fields
        tags_raw = form.get("tags", "")
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()]

        resources_raw = form.get("resources", "")
        resources = [r.strip() for r in resources_raw.splitlines() if r.strip()]

        data = {
            "id_": question.id_,
            "question": form.get("question_text", ""),
            "answers": answers,
            "tags": tags,
            "question_type": question.question_type,
            "explanation": form.get("explanation", ""),
            "version": question.version,
            "resources": resources,
            "meta": question.meta.model_dump(),
        }

        # Keep form data for re-rendering on error
        form_data = {
            "question_text": data["question"],
            "answers": answers,
            "tags": tags_raw,
            "explanation": data["explanation"],
            "resources": resources_raw,
        }

        try:
            updated = ChoiceQuestion.model_validate(data)
        except ValidationError as e:
            error = str(e)
            return render_template(
                "edit_question.html",
                question=question,
                form_data=form_data,
                error=error,
                referrer=referrer,
                quiz_index=quiz_index,
            )

        # Persist to the original source path for this question.
        file_path = POOL.get_question_path_by_id(updated.id_)
        file_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n"
        )

        # Update the in-memory pool
        for i, q in enumerate(POOL.questions):
            if q.id_ == updated.id_:
                POOL.questions[i] = updated
                break

        return redirect(url_for("edit_question", question_id=updated.id_))

    # GET: populate form_data from the current question
    form_data = {
        "question_text": question.question,
        "answers": [
            {"text": a.text, "correct": a.correct, "rationale": a.rationale}
            for a in question.answers
        ],
        "tags": ", ".join(question.tags),
        "explanation": question.explanation,
        "resources": "\n".join(question.resources),
    }

    return render_template(
        "edit_question.html",
        question=question,
        form_data=form_data,
        error=error,
        referrer=referrer,
        quiz_index=quiz_index,
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
    prepare_quiz_session(available_questions, saved_quiz_id=quiz_id)

    return redirect(url_for("quiz_question", index=0))


@app.route("/history/<quiz_id>/delete", methods=["POST"])
def delete_saved_quiz(quiz_id: str):
    """Delete a saved quiz from history."""
    QUIZ_STORE.delete_quiz(quiz_id)
    return redirect(url_for("history"))
