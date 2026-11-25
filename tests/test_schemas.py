from datetime import datetime

import pytest
from pydantic import ValidationError

from sprintpilot.models import (
    Approval,
    ApprovalStatus,
    Epic,
    Priority,
    ProjectAnalysis,
    ProjectBrief,
    Severity,
    Sprint,
    SprintPlan,
    Task,
    TaskDependency,
    TaskStatus,
    UserStory,
)


def test_project_brief_accepts_valid_local_project() -> None:
    brief = ProjectBrief(
        name="Campus Marketplace",
        description="A marketplace for students.",
        goals=["Help students exchange books"],
        features=["Listings", "Messaging"],
        team_size=4,
        duration_weeks=8,
        sprint_capacity=20,
    )

    assert brief.team_size == 4
    assert brief.capacity_unit == "points"


@pytest.mark.parametrize("field,value", [
    ("team_size", 0),
    ("duration_weeks", 0),
    ("sprint_capacity", 0),
])
def test_project_brief_rejects_invalid_planning_values(field: str, value: int) -> None:
    data = {
        "name": "Test project",
        "description": "A test project.",
        field: value,
    }

    with pytest.raises(ValidationError):
        ProjectBrief.model_validate(data)


def test_backlog_models_keep_relationship_ids() -> None:
    epic = Epic(id="E-1", title="Authentication", description="User access")
    story = UserStory(
        id="US-1",
        epic_id=epic.id,
        text="As a student, I want to sign in so that I can access my account.",
        priority=Priority.HIGH,
        acceptance_criteria=["Valid credentials grant access"],
    )
    task = Task(
        id="T-1",
        user_story_id=story.id,
        description="Create login form",
        estimate=3,
        status=TaskStatus.TODO,
    )
    dependency = TaskDependency(task_id="T-2", depends_on_task_id=task.id)

    assert story.epic_id == epic.id
    assert task.user_story_id == story.id
    assert dependency.depends_on_task_id == task.id


def test_task_rejects_estimate_outside_allowed_fibonacci_values() -> None:
    with pytest.raises(ValidationError):
        Task(
            id="T-1",
            user_story_id="US-1",
            description="Invalid estimate",
            estimate=4,
        )


def test_sprint_plan_accepts_nested_models() -> None:
    plan = SprintPlan(
        project_id="P-1",
        analysis=ProjectAnalysis(
            summary="A local marketplace.",
            features=["Listings"],
        ),
        sprints=[
            Sprint(
                number=1,
                capacity=20,
                task_ids=["T-1"],
                workload=5,
            )
        ],
    )

    assert plan.analysis.features == ["Listings"]
    assert plan.sprints[0].workload == 5


def test_approval_and_model_enums_are_structured() -> None:
    approved_at = datetime(2026, 11, 24, 12, 0)
    approval = Approval(
        status=ApprovalStatus.APPROVED,
        decided_at=approved_at,
        comment="Plan reviewed",
    )

    assert approval.status == ApprovalStatus.APPROVED
    assert approval.decided_at == approved_at


def test_extra_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        Epic.model_validate({
            "id": "E-1",
            "title": "Auth",
            "description": "Authentication",
            "unexpected": "value",
        })
