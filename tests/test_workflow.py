import sprintpilot.workflow as workflow_module
from sprintpilot.knowledge import RetrievedGuideline
from sprintpilot.workflow import (
    backlog_generator,
    correction_node,
    human_approval,
    route_review,
)
from sprintpilot.models import (
    BacklogGenerationResult,
    ProjectAnalysis,
    ProjectBrief,
    SprintPlan,
)


def test_correction_attempt_is_bounded() -> None:
    state = {"correction_attempts": 1}

    result = correction_node(state)

    assert result["correction_attempts"] == 2


def test_review_routes_ready_plan_to_human_approval() -> None:
    state = {"status": "ready_for_approval"}

    assert route_review(state) == "human_approval"


def test_review_routes_critical_plan_to_human_decision() -> None:
    state = {"status": "critical_issues"}

    assert route_review(state) == "human_decision"


def test_human_approval_requires_approved_state() -> None:
    plan = SprintPlan(
        project_id="P",
        analysis=ProjectAnalysis(summary="Test"),
    )
    pending = human_approval({"plan": plan, "approval_status": "pending"})
    approved = human_approval({"plan": plan, "approval_status": "approved"})

    assert pending["status"] == "waiting_for_approval"
    assert approved["status"] == "approved"


def test_backlog_node_passes_retrieved_guidelines(monkeypatch) -> None:
    expected_guideline = RetrievedGuideline(
        source="sprint_planning.md",
        text="Plan work within team capacity.",
        score=0.1,
    )
    captured = {}

    def fake_generate_backlog(brief, analysis, *, guidelines):
        captured["guidelines"] = guidelines
        return BacklogGenerationResult()

    monkeypatch.setattr(
        workflow_module,
        "generate_backlog",
        fake_generate_backlog,
    )
    state = {
        "brief": ProjectBrief(name="Project", description="A test project."),
        "analysis": ProjectAnalysis(summary="A test project."),
        "guidelines": [expected_guideline],
    }

    result = backlog_generator(state)

    assert captured["guidelines"] == [expected_guideline]
    assert result["backlog"] == BacklogGenerationResult()
