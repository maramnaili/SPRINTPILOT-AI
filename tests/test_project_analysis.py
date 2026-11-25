from types import SimpleNamespace

import httpx
import pytest
from openai import APIConnectionError, APITimeoutError

from sprintpilot.models import ProjectAnalysis, ProjectBrief
from sprintpilot.analysis import analyze_project_brief


class MockParser:
    def __init__(self, parsed: ProjectAnalysis | None) -> None:
        self.parsed = parsed

    def parse(self, **kwargs: object) -> object:
        message = SimpleNamespace(parsed=self.parsed)
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice])


class MockChat:
    def __init__(self, parsed: ProjectAnalysis | None) -> None:
        self.completions = MockParser(parsed)


class MockClient:
    def __init__(self, parsed: ProjectAnalysis | None) -> None:
        self.chat = MockChat(parsed)


class MockFailingParser:
    def __init__(self, exception: Exception) -> None:
        self.exception = exception

    def parse(self, **kwargs: object) -> object:
        raise self.exception


class MockFailingChat:
    def __init__(self, exception: Exception) -> None:
        self.completions = MockFailingParser(exception)


class MockFailingClient:
    def __init__(self, exception: Exception) -> None:
        self.chat = MockFailingChat(exception)


def valid_brief() -> ProjectBrief:
    return ProjectBrief(
        name="Study Planner",
        description="A web application that helps students organize study tasks.",
        goals=["Improve weekly planning"],
        features=["Task list", "Calendar"],
        constraints=["Keep data local"],
        team_size=3,
        duration_weeks=6,
        sprint_capacity=18,
    )


def test_analyze_project_brief_returns_parsed_project_analysis() -> None:
    expected = ProjectAnalysis(
        summary="A local study planning application.",
        goals=["Improve weekly planning"],
        features=["Task list", "Calendar"],
        constraints=["Keep data local"],
        assumptions=["A small student team"],
        ambiguities=["Authentication is not specified"],
        clarification_questions=["Should accounts be local-only?"],
    )
    mock_client = MockClient(expected)
    result = analyze_project_brief(valid_brief(), client=mock_client)

    assert result == expected
    assert result.summary == "A local study planning application."


def test_analyze_project_brief_rejects_empty_parsed_result() -> None:
    with pytest.raises(RuntimeError, match="did not contain a parsed ProjectAnalysis"):
        analyze_project_brief(valid_brief(), client=MockClient(None))


@pytest.mark.parametrize(
    ("exception", "message"),
    [
        (
            APITimeoutError(request=httpx.Request("POST", "http://localhost:11434/v1")),
            "timed out",
        ),
        (
            APIConnectionError(request=httpx.Request("POST", "http://localhost:11434/v1")),
            "Could not connect to Ollama",
        ),
    ],
)
def test_analyze_project_brief_handles_connection_errors(
    exception: Exception,
    message: str,
) -> None:
    with pytest.raises(RuntimeError, match=message):
        analyze_project_brief(valid_brief(), client=MockFailingClient(exception))
