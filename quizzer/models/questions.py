
from datetime import datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class ChoiceAnswer(BaseModel):
    """Answer to a question which can be correct or incorrect. The rationale 
    describes why it would be correct or incorrect.
    """
    text: str
    correct: bool
    rationale: str


class QuestionMetaInfo(BaseModel):
    """Meta information on a question"""
    origin: str
    official: bool
    created: datetime
    raw_file_index: Optional[int] = None


class ChoiceQuestion(BaseModel):
    """A question with one or multiple correct answers"""
    id_: str
    question: str
    answers: list[ChoiceAnswer]
    tags: list[str]
    question_type: str
    explanation: str
    version: str
    resources: list[str] = Field(default_factory=list)
    meta: QuestionMetaInfo

    @field_validator("id_")
    @classmethod
    def validate_uuid4(cls, v: str) -> str:
        try:
            uuid = UUID(v, version=4)
        except ValueError:
            raise ValueError("id_ must be a valid UUID4 string")
        if str(uuid) != v:
            raise ValueError("id_ must be a valid UUID4 string")
        return v

    @field_validator("answers")
    @classmethod
    def validate_answers(cls, answers: list[ChoiceAnswer]) -> list[ChoiceAnswer]:
        if len(answers) < 2:
            raise ValueError("A choice question must have at least two answers")
        if not any(answer.correct for answer in answers):
            raise ValueError("At least one answer to a choice question must be correct")
        return answers

