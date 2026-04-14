# quizzer

Simple, extensible quiz application for self-study and exam preparation.

## How It Works

1. **Question Pool** (`./data/questions`) - Put questions which you want to use into this directory (see `quizzer.models.questions.ChoiceQuestion` for expected format)
2. **Run the App** - Start the Flask app (e.g. via `python -m quizzer.main`) and navigate to `http://localhost:5000`
3. **Home Page** (`/`) - Select one or more questions from the available pool and click **Start Quiz**
4. **Quiz** Answer questions and review your progress (answered, skipped, unanswered counts) before finalizing


## Features

- **Question Selection** — Browse available questions and customize selection for your quiz
- **Multiple Answer Types** — Support for single-choice and multiple-choice questions
- **Detailed Review** — After completing the quiz, review each question with correct answers and explanations
