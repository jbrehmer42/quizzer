import random
from collections import Counter

from quizzer.models.questions import ChoiceQuestion



def sample_questions_by_tags(
    questions: list[ChoiceQuestion], tags: set[str], max_questions: int
) -> list[ChoiceQuestion]:
    """Randomly sample questions from the given tags and ensure a balanced
    distribution of tags by always selecting questions from the least represented
    tag first.

    Each tag is guaranteed at least one question (if available and max_questions
    permits). The total number of questions is capped at max_questions.
    """
    questions_by_tag = {
        tag: [q for q in questions if tag in q.tags]
        for tag in tags
    }
    selected_ids: set[str] = set()
    selected: list[ChoiceQuestion] = []

    tag_counter = Counter({tag: 0 for tag in tags})
    while len(selected) < max_questions and tag_counter:
        # Select a tag with the least number of questions selected so far
        tag = tag_counter.most_common()[-1][0]
        if not questions_by_tag[tag]:
            del tag_counter[tag]
            continue
        # Choose random question for that tag and remove it from the
        # available choices for that tag
        index = random.choice(range(len(questions_by_tag[tag])))
        question = questions_by_tag[tag].pop(index)
        if question.id_ not in selected_ids:
            selected.append(question)
            selected_ids.add(question.id_)
            tag_counter.update(
                tag for tag in question.tags if tag in tag_counter
            )
    
    return selected