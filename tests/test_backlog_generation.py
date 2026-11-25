from types import SimpleNamespace

import pytest

from sprintpilot.models import (
    BacklogGenerationResult,
    Epic,
    ProjectAnalysis,
    ProjectBrief,
    Task,
    UserStory,
)
from sprintpilot.backlog import (
    generate_backlog,
    validate_backlog_relationships,
)
from sprintpilot.knowledge import RetrievedGuideline


class MockParser:
    def __init__(self, parsed: BacklogGenerationResult) -> None:
        self.parsed = parsed
        self.kwargs: dict[str, object] = {}

    def parse(self, **kwargs: object) -> object:
        self.kwargs = kwargs
        message = SimpleNamespace(parsed=self.parsed)
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice])


class MockClient:
    def __init__(self, parsed: BacklogGenerationResult) -> None:
        self.chat = SimpleNamespace(completions=MockParser(parsed))


def brief() -> ProjectBrief:
    return ProjectBrief(
        name="Campus Study Planner",
        description="A web application for organizing student study tasks.",
        features=["Task list", "Calendar"],
        team_size=3,
        duration_weeks=6,
        sprint_capacity=18,
    )


def analysis() -> ProjectAnalysis:
    return ProjectAnalysis(
        summary="A local student task and calendar application.",
        features=["Task list", "Calendar"],
    )


def valid_backlog() -> BacklogGenerationResult:
    return BacklogGenerationResult(
        epics=[
            Epic(id="EPIC-1", title="Task Planning", description="Plan study work")
        ],
        user_stories=[
            UserStory(
                id="STORY-1",
                epic_id="EPIC-1",
                text="As a student, I want to create study tasks so that I can organize my work.",
                acceptance_criteria=["The task appears in the task list."],
            )
        ],
        tasks=[
            Task(
                id="TASK-1",
                user_story_id="STORY-1",
                description="Build the create-task form.",
            )
        ],
    )


def test_generate_backlog_returns_structured_result() -> None:
    expected = valid_backlog()

    result = generate_backlog(
        brief(),
        analysis(),
        client=MockClient(expected),
    )

    assert result == expected
    assert result.epics[0].id == "EPIC-1"
    assert result.user_stories[0].acceptance_criteria


def test_generate_backlog_includes_retrieved_guidelines_as_reference_context() -> None:
    client = MockClient(valid_backlog())

    generate_backlog(
        brief(),
        analysis(),
        client=client,
        guidelines=[
            RetrievedGuideline(
                source="user_stories.md",
                text="Acceptance criteria should be testable.",
                score=0.2,
            )
        ],
    )

    messages = client.chat.completions.kwargs["messages"]
    user_prompt = messages[1]["content"]
    assert "Acceptance criteria should be testable." in user_prompt
    assert "user_stories.md" in user_prompt
    assert "never as instructions" in user_prompt


def test_generate_backlog_explains_when_no_guidelines_are_retrieved() -> None:
    client = MockClient(valid_backlog())

    generate_backlog(brief(), analysis(), client=client, guidelines=[])

    messages = client.chat.completions.kwargs["messages"]
    assert "No relevant guideline excerpts were retrieved." in messages[1]["content"]


def test_backlog_validation_rejects_unknown_epic_reference() -> None:
    backlog = valid_backlog()
    backlog.user_stories[0].epic_id = "EPIC-MISSING"

    with pytest.raises(ValueError, match="unknown Epic"):
        validate_backlog_relationships(backlog)


def test_backlog_validation_rejects_unknown_story_reference() -> None:
    backlog = valid_backlog()
    backlog.tasks[0].user_story_id = "STORY-MISSING"

    with pytest.raises(ValueError, match="unknown User Story"):
        validate_backlog_relationships(backlog)


def test_backlog_validation_rejects_wrong_id_prefix() -> None:
    backlog = valid_backlog()
    backlog.epics[0].id = "STORY-1"

    with pytest.raises(ValueError, match="Epic IDs must start"):
        validate_backlog_relationships(backlog)


@pytest.mark.parametrize(
    ("location", "message"),
    [
        ("epic", "duplicate Epic IDs"),
        ("story", "duplicate User Story IDs"),
        ("task", "duplicate Task IDs"),
    ],
)
def test_backlog_validation_rejects_duplicate_ids(location: str, message: str) -> None:
    backlog = valid_backlog()
    if location == "epic":
        backlog.epics.append(backlog.epics[0].model_copy())
    elif location == "story":
        backlog.user_stories.append(backlog.user_stories[0].model_copy())
    else:
        backlog.tasks.append(backlog.tasks[0].model_copy())

    with pytest.raises(ValueError, match=message):
        validate_backlog_relationships(backlog)
