from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from sprintpilot.models import (
    BacklogGenerationResult,
    ProjectAnalysis,
    ProjectBrief,
    SprintPlan,
)
from sprintpilot.analysis import analyze_project_brief
from sprintpilot.backlog import generate_backlog
from sprintpilot.planning import (
    analyze_dependencies,
    assign_sprints,
    calculate_sprint_capacity,
    estimate_task_effort,
    review_plan,
)
from sprintpilot.knowledge import RetrievedGuideline, retrieve_project_guidelines


class WorkflowState(TypedDict, total=False):
    brief: ProjectBrief
    analysis: ProjectAnalysis
    backlog: BacklogGenerationResult
    plan: SprintPlan
    guidelines: list[RetrievedGuideline]
    correction_attempts: int
    approval_status: Literal["pending", "approved", "rejected"]
    status: str
    warnings: list[str]


def project_analyzer(state: WorkflowState) -> WorkflowState:
    return {
        **state,
        "analysis": analyze_project_brief(state["brief"]),
    }


def retrieve_guidelines(state: WorkflowState) -> WorkflowState:
    brief = state["brief"]
    query = (
        f"{brief.name} {brief.description} "
        f"{' '.join(brief.goals)} {' '.join(brief.features)}"
    )
    guidelines = retrieve_project_guidelines(query, max_results=3)
    return {**state, "guidelines": guidelines}


def backlog_generator(state: WorkflowState) -> WorkflowState:
    backlog = generate_backlog(
        state["brief"],
        state["analysis"],
        guidelines=state.get("guidelines", []),
    )
    return {**state, "backlog": backlog}


def effort_estimator(state: WorkflowState) -> WorkflowState:
    backlog = state["backlog"]
    for task in backlog.tasks:
        estimate, _ = estimate_task_effort(task)
        task.estimate = estimate
    return {**state, "backlog": backlog}


def dependency_analyzer(state: WorkflowState) -> WorkflowState:
    plan = state.get("plan")
    if plan is None:
        plan = SprintPlan(
            project_id=state["brief"].name,
            analysis=state["analysis"],
            epics=state["backlog"].epics,
            user_stories=state["backlog"].user_stories,
            tasks=state["backlog"].tasks,
        )

    dependencies = plan.dependencies
    result = analyze_dependencies(plan.tasks, dependencies)
    warnings = result.errors
    if not result.valid:
        warnings = result.errors
    return {**state, "plan": plan, "warnings": warnings}


def sprint_planner(state: WorkflowState) -> WorkflowState:
    plan = state["plan"]
    brief = state["brief"]
    capacities = calculate_sprint_capacity(
        brief.sprint_capacity,
        brief.duration_weeks,
        capacity_unit=brief.capacity_unit,
    )
    sprints, unassigned = assign_sprints(
        plan.tasks,
        plan.dependencies,
        brief.sprint_capacity,
        len(capacities),
    )
    plan.sprints = sprints
    plan.unassigned_task_ids = unassigned
    return {**state, "plan": plan}


def reviewer(state: WorkflowState) -> WorkflowState:
    issues = review_plan(state["plan"])
    state["plan"].review_issues = issues
    correctable = [
        issue for issue in issues
        if issue.severity.value in {"low", "medium", "high"}
    ]
    status = "reviewed"
    if any(issue.severity.value == "critical" for issue in issues):
        status = "critical_issues"
    elif not issues:
        status = "ready_for_approval"
    elif state.get("correction_attempts", 0) >= 2:
        status = "human_decision_required"
    elif correctable:
        status = "needs_correction"
    return {**state, "status": status}


def correction_node(state: WorkflowState) -> WorkflowState:
    attempts = state.get("correction_attempts", 0) + 1
    plan = state.get("plan")
    if plan is not None:
        for task in plan.tasks:
            if task.estimate not in (1, 2, 3, 5, 8):
                estimate, _ = estimate_task_effort(task)
                task.estimate = estimate
        for story in plan.user_stories:
            if not story.acceptance_criteria:
                story.acceptance_criteria = [
                    "The implemented behavior can be demonstrated and verified."
                ]
    return {
        **state,
        "plan": plan,
        "correction_attempts": attempts,
        "warnings": [
            f"Correction attempt {attempts}: review issues will be revalidated."
        ],
    }


def human_approval(state: WorkflowState) -> WorkflowState:
    if state.get("approval_status") == "approved":
        state["plan"].approval.status = "approved"
        state["status"] = "approved"
    else:
        state["status"] = "waiting_for_approval"
    return state


def route_review(state: WorkflowState) -> Literal[
    "correction",
    "human_approval",
    "human_decision",
]:
    if state["status"] == "needs_correction":
        return "correction"
    if state["status"] == "ready_for_approval":
        return "human_approval"
    return "human_decision"


def correction_router(state: WorkflowState) -> Literal["effort_estimator", "reviewer"]:
    if state.get("correction_attempts", 0) <= 2:
        return "effort_estimator"
    return "reviewer"


def build_workflow():
    builder = StateGraph(WorkflowState)
    builder.add_node("project_analyzer", project_analyzer)
    builder.add_node("retrieve_guidelines", retrieve_guidelines)
    builder.add_node("backlog_generator", backlog_generator)
    builder.add_node("effort_estimator", effort_estimator)
    builder.add_node("dependency_analyzer", dependency_analyzer)
    builder.add_node("sprint_planner", sprint_planner)
    builder.add_node("reviewer", reviewer)
    builder.add_node("correction", correction_node)
    builder.add_node("human_approval", human_approval)

    builder.add_edge(START, "project_analyzer")
    builder.add_edge("project_analyzer", "retrieve_guidelines")
    builder.add_edge("retrieve_guidelines", "backlog_generator")
    builder.add_edge("backlog_generator", "effort_estimator")
    builder.add_edge("effort_estimator", "dependency_analyzer")
    builder.add_edge("dependency_analyzer", "sprint_planner")
    builder.add_edge("sprint_planner", "reviewer")
    builder.add_conditional_edges(
        "reviewer",
        route_review,
        {
            "correction": "correction",
            "human_approval": "human_approval",
            "human_decision": "human_approval",
        },
    )
    builder.add_conditional_edges(
        "correction",
        correction_router,
        {
            "effort_estimator": "effort_estimator",
            "reviewer": "reviewer",
        },
    )
    builder.add_edge("human_approval", END)
    return builder.compile()
