from types import SimpleNamespace

from fastapi.testclient import TestClient

import sprintpilot.api as api_module
from sprintpilot.api import app
from sprintpilot.database import create_tables
from sprintpilot.knowledge import RetrievedGuideline
from sprintpilot.models import (
    BacklogGenerationResult,
    ProjectAnalysis,
    ProjectBrief,
)


client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_project_endpoint() -> None:
    create_tables()
    response = client.post(
        "/projects",
        json={
            "name": "API Test Project",
            "description": "A project created by the API test.",
            "team_size": 2,
            "duration_weeks": 4,
            "sprint_capacity": 10,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "API Test Project"
    assert body["approval_status"] == "pending"

    project_response = client.get(f"/projects/{body['id']}")

    assert project_response.status_code == 200
    assert project_response.json()["brief"]["name"] == "API Test Project"


def test_export_missing_plan_returns_not_found() -> None:
    create_tables()
    response = client.post(
        "/projects",
        json={
            "name": "Export Test",
            "description": "A project used to verify JSON export.",
        },
    )
    project_id = response.json()["id"]

    export_response = client.get(f"/projects/{project_id}/export")

    assert export_response.status_code == 404


def test_generate_endpoint_passes_retrieved_guidelines_to_backlog(monkeypatch) -> None:
    brief = ProjectBrief(name="RAG API Test", description="A test project.")
    analysis = ProjectAnalysis(summary="A test project.")
    guideline = RetrievedGuideline(
        source="acceptance_criteria.md",
        text="Acceptance criteria must be testable.",
        score=0.1,
    )
    captured = {}

    monkeypatch.setattr(
        api_module,
        "fetch_project",
        lambda project_id: SimpleNamespace(
            id=project_id,
            name=brief.name,
            brief_json=brief.model_dump(mode="json"),
        ),
    )
    monkeypatch.setattr(
        api_module,
        "analyze_project_brief",
        lambda project_brief: analysis,
    )
    monkeypatch.setattr(
        api_module,
        "retrieve_project_guidelines",
        lambda query, max_results: [guideline],
    )

    def fake_generate_backlog(project_brief, project_analysis, *, guidelines):
        captured["guidelines"] = guidelines
        return BacklogGenerationResult()

    monkeypatch.setattr(api_module, "generate_backlog", fake_generate_backlog)
    monkeypatch.setattr(api_module, "save_project", lambda **kwargs: None)

    result = api_module.generate_project(123)

    assert captured["guidelines"] == [guideline]
    assert result["guideline_sources"] == ["acceptance_criteria.md"]
