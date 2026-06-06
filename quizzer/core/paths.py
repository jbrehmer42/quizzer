from pathlib import Path
from typing import Final


DATA_PATH: Final[Path] = Path(__file__).parent.parent.parent / "data"
PERSISTENCE_PATH: Final[Path] = DATA_PATH / "saved_quizzes.json"
