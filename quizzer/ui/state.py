from typing import Final

from quizzer.models.quiz import QuizSession
from quizzer.models.settings import Settings


class AppState:
    """In-memory application state. Holds quiz sessions and user settings.

    Designed to be subclassed or replaced for persistent storage.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, QuizSession] = {}
        self.settings: Settings = Settings()

    def put(self, quiz_id: str, quiz_session: QuizSession) -> None:
        self._sessions[quiz_id] = quiz_session

    def get(self, quiz_id: str) -> QuizSession | None:
        return self._sessions.get(quiz_id)

    def delete(self, quiz_id: str) -> None:
        self._sessions.pop(quiz_id, None)


STATE: Final[AppState] = AppState()
