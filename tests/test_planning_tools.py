from datetime import datetime

import pytest

from sprintpilot.models import (
    Approval,
    ApprovalStatus,
    Epic,
    Priority,
    ProjectAnalysis,
    Sprint,
    SprintPlan,
    Task,
    TaskDependency,
    UserStory,
)
from sprintpilot.planning import (
    analyze_dependencies,
    assign_sprints,
    calculate_sprint_capacity,
    estimate_task_effort,
    review_plan,
    save_approved_plan,
)


def test_estimation_is_explainable_and_fibonacci_bounded() -> None:
    task = Task(
        id="TASK-1",
        user_story_id="STORY-1",
        description="Build payment integration",
        priority=Priority.HIGH,
    )

    estimate, reason = estimate_task_effort(task)

    assert estimate in {1, 2, 3, 5, 8}
    assert "complexity" in reason.lower() or "risk" in reason.lower()


def test_dependency_cycle_is_detected() -> None:
    tasks = [
        Task(id="A", user_story_id="S", description="Task A"),
        Task(id="B", user_story_id="S", description="Task B"),
    ]
    dependencies = [
        TaskDependency(task_id="A", depends_on_task_id="B"),
        TaskDependency(task_id="B", depends_on_task_id="A"),
    ]

    result = analyze_dependencies(tasks, dependencies)

    assert not result.valid
    assert result.cycles
    assert any("cycle" in error.lower() for error in result.errors)


def test_dependency_order_respects_prerequisites() -> None:
    tasks = [
        Task(id="A", user_story_id="S", description="Task A"),
        Task(id="B", user_story_id="S", description="Task B"),
        Task(id="C", user_story_id="S", description="Task C"),
    ]
    dependencies = [
        TaskDependency(task_id="B", depends_on_task_id="A"),
        TaskDependency(task_id="C", depends_on_task_id="B"),
    ]

    result = analyze_dependencies(tasks, dependencies)

    assert result.valid
    assert result.execution_order.index("A") < result.execution_order.index("B")
    assert result.execution_order.index("B") < result.execution_order.index("C")


def test_sprint_capacity_calculation_uses_two_week_sprints() -> None:
    capacities = calculate_sprint_capacity(20, 6)

    assert capacities == [20.0, 20.0, 20.0]


def test_sprint_assignment_reports_over_capacity_tasks() -> None:
    tasks = [
        Task(
            id="A",
            user_story_id="S",
            description="Task A",
            estimate=8,
        ),
        Task(
            id="B",
            user_story_id="S",
            description="Task B",
            estimate=5,
        ),
    ]

    sprints, unassigned = assign_sprints(tasks, [], 5, 1)

    assert unassigned == ["A"]
    assert sprints[0].task_ids == ["B"]


def test_review_plan_finds_missing_acceptance_criteria() -> None:
    plan = SprintPlan(
        project_id="P",
        analysis=ProjectAnalysis(summary="Test application"),
        epics=[Epic(id="E", title="Epic", description="Epic description")],
        user_stories=[
            UserStory(
                id="S",
                epic_id="E",
                text="As a user, I want to test so that it works.",
                acceptance_criteria=["It works."],
            )
        ],
        tasks=[],
    )
    plan.user_stories[0].acceptance_criteria = []

    issues = review_plan(plan)

    assert any(issue.code == "MISSING_ACCEPTANCE_CRITERIA" for issue in issues)


def test_save_approved_plan_requires_explicit_approval() -> None:
    plan = SprintPlan(
        project_id="P",
        analysis=ProjectAnalysis(summary="Test application"),
    )

    with pytest.raises(ValueError, match="explicit approval"):
        save_approved_plan(plan, Approval(status=ApprovalStatus.PENDING))

    approval = Approval(
        status=ApprovalStatus.APPROVED,
        decided_at=datetime(2026, 11, 24),
        comment="Reviewed",
    )
    assert save_approved_plan(plan, approval)
