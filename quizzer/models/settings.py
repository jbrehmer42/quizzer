from typing import Any, ClassVar

from pydantic import BaseModel, Field


class SettingField(BaseModel):
    """Describes a single displayable/editable setting for template rendering."""

    form_name: str
    label: str
    description: str
    value: Any


class SettingsSection(BaseModel):
    """Base class for a named group of related settings.

    Subclasses must declare `_section_title` and `_form_prefix` as class
    variables and define their individual settings as Pydantic fields.

    The section itself owns both the rendering contract (`title`, `fields`)
    and the update logic (`apply_form`).
    """

    _section_title: ClassVar[str]
    _form_prefix: ClassVar[str]

    @property
    def title(self) -> str:
        return self._section_title

    @property
    def fields(self) -> list[SettingField]:
        """Return all settings in this section as renderable field objects."""
        return [
            SettingField(
                form_name=self.get_form_field_name(field_name),
                label=field_info.title,
                description=field_info.description or "",
                value=getattr(self, field_name),
            )
            for field_name, field_info in type(self).model_fields.items()
        ]

    def get_form_field_name(self, field_name: str) -> str:
        """Return the expected HTML form key for a given field name."""
        return f"{self._form_prefix}.{field_name}"

    def apply_form(self, form: dict[str, str]) -> None:
        """Update this section's fields in-place from an HTML form dict.

        Currently supports only bool fields (checkboxes).
        """
        for field_name in type(self).model_fields.keys():
            key = self.get_form_field_name(field_name)
            current = getattr(self, field_name)
            if isinstance(current, bool):
                setattr(self, field_name, key in form)


class QuizSettings(SettingsSection):
    """Settings that control quiz generation behaviour."""

    _section_title: ClassVar[str] = "Quiz"
    _form_prefix: ClassVar[str] = "quiz"

    randomize_question_order: bool = Field(
        default=True,
        title="Randomize question order",
        description="Questions will be presented in a different shuffled order each session.",
    )
    randomize_answer_order: bool = Field(
        default=True,
        title="Randomize answer order",
        description="Answer choices will be shuffled independently for each question each session.",
    )


class Settings(BaseModel):
    """Application-wide settings, composed of typed sub-settings objects."""

    quiz: QuizSettings = Field(default_factory=QuizSettings)

    @property
    def sections(self) -> list[SettingsSection]:
        """Return all sub-settings sections for template rendering."""
        _sections = (getattr(self, name) for name in type(self).model_fields.keys())
        return [
            sec for sec in _sections
            if isinstance(sec, SettingsSection)
        ]

    def apply_form(self, form: dict[str, str]) -> None:
        """Distribute an HTML form submission to each sub-settings section."""
        for section in self.sections:
            section.apply_form(form)


