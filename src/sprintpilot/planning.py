from dataclasses import dataclass

from sprintpilot.models import (
    Priority,
    ReviewIssue,
    Severity,
    Sprint,
    SprintPlan,
    Task,
    TaskDependency,
)


FIBONACCI_ESTIMATES = (1, 2, 3, 5, 8)


def estimate_task_effort(task: Task) -> tuple[int, str]:
    """Apply a simple explainable Fibonacci rule to a task."""

    text = task.description.lower()
    length = len(text)
    complexity_words = ("database", "security", "authentication", "payment", "integration", "migration")
    uncertainty_words = ("research", "unknown", "prototype", "unclear")

    if any(word in text for word in ("payment", "security", "migration")):
        estimate = 8
        reason = "High technical risk or cross-system complexity: 8 story points."
    elif task.priority == Priority.HIGH or any(word in text for word in complexity_words):
        estimate = 5
        reason = "High priority or technical complexity: 5 story points."
    elif any(word in text for word in uncertainty_words) or length > 90:
        estimate = 3
        reason = "Moderate uncertainty or description complexity: 3 story points."
    elif len(text.split()) <= 4:
        estimate = 1
        reason = "Small, clearly bounded task: 1 story point."
    else:
        estimate = 2
        reason = "Small implementation task with limited uncertainty: 2 story points."

    if estimate not in FIBONACCI_ESTIMATES:
        estimate = 3
    return estimate, reason


@dataclass
class DependencyResult:
    valid: bool
    execution_order: list[str]
    cycles: list[list[str]]
    errors: list[str]


def analyze_dependencies(
    tasks: list[Task],
    dependencies: list[TaskDependency],
) -> DependencyResult:
    task_ids = {task.id for task in tasks}
    adjacency = {task_id: [] for task_id in task_ids}
    errors: list[str] = []

    for dependency in dependencies:
        if dependency.task_id not in task_ids:
            errors.append(
                f"Dependency references unknown task {dependency.task_id}."
            )
            continue
        if dependency.depends_on_task_id not in task_ids:
            errors.append(
                f"Task {dependency.task_id} depends on unknown task "
                f"{dependency.depends_on_task_id}."
            )
            continue
        adjacency[dependency.task_id].append(dependency.depends_on_task_id)

    color = {task_id: 0 for task_id in task_ids}
    stack: list[str] = []
    cycles: list[list[str]] = []

    def visit(task_id: str) -> None:
        color[task_id] = 1
        stack.append(task_id)
        for prerequisite in adjacency[task_id]:
            if color[prerequisite] == 0:
                visit(prerequisite)
            elif color[prerequisite] == 1:
                start = stack.index(prerequisite)
                cycles.append(stack[start:] + [prerequisite])
        stack.pop()
        color[task_id] = 2

    for task_id in task_ids:
        if color[task_id] == 0:
            visit(task_id)

    if cycles:
        for cycle in cycles:
            errors.append("Dependency cycle detected: " + " -> ".join(cycle))

    if cycles or errors:
        return DependencyResult(False, [], cycles, errors)

    remaining = set(task_ids)
    assigned: set[str] = set()
    order: list[str] = []
    while remaining:
        ready = [
            task_id
            for task_id in remaining
            if all(prerequisite in assigned for prerequisite in adjacency[task_id])
        ]
        if not ready:
            break
        ready.sort()
        for task_id in ready:
            order.append(task_id)
            assigned.add(task_id)
            remaining.remove(task_id)

    return DependencyResult(not remaining, order, cycles, errors)


def calculate_sprint_capacity(
    sprint_capacity: float,
    duration_weeks: int,
    *,
    capacity_unit: str = "points",
) -> list[float]:
    if sprint_capacity <= 0:
        raise ValueError("Sprint capacity must be greater than zero.")
    if duration_weeks <= 0:
        raise ValueError("Duration must be greater than zero.")
    if capacity_unit not in {"points", "hours"}:
        raise ValueError("Capacity unit must be 'points' or 'hours'.")

    sprint_count = max(1, (duration_weeks + 1) // 2)
    return [float(sprint_capacity) for _ in range(sprint_count)]


def assign_sprints(
    tasks: list[Task],
    dependencies: list[TaskDependency],
    sprint_capacity: float,
    sprint_count: int,
) -> tuple[list[Sprint], list[str]]:
    if sprint_capacity <= 0:
        raise ValueError("Sprint capacity must be greater than zero.")
    if sprint_count <= 0:
        raise ValueError("Sprint count must be greater than zero.")

    dependency_result = analyze_dependencies(tasks, dependencies)
    if not dependency_result.valid:
        warnings = dependency_result.errors
        sprints = [
            Sprint(number=index + 1, capacity=sprint_capacity)
            for index in range(sprint_count)
        ]
        return sprints, [task.id for task in tasks]

    sprints = [
        Sprint(number=index + 1, capacity=sprint_capacity)
        for index in range(sprint_count)
    ]
    assigned: set[str] = set()
    unassigned: list[str] = []
    task_lookup = {task.id: task for task in tasks}

    priority_rank = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}

    for task_id in dependency_result.execution_order:
        task = task_lookup[task_id]
        estimate = task.estimate or 3
        placed = False

        for sprint in sprints:
            prerequisites = [
                dependency.depends_on_task_id
                for dependency in dependencies
                if dependency.task_id == task_id
            ]
            if not all(item in assigned for item in prerequisites):
                continue
            if sprint.workload + estimate <= sprint.capacity:
                sprint.task_ids.append(task_id)
                sprint.workload += estimate
                assigned.add(task_id)
                placed = True
                break

        if not placed:
            unassigned.append(task_id)

    for sprint in sprints:
        if sprint.workload > sprint.capacity:
            sprint.warnings.append("Sprint capacity exceeded.")

    unassigned.sort(key=lambda task_id: (
        priority_rank[task_lookup[task_id].priority],
        task_lookup[task_id].id,
    ))
    return sprints, unassigned


def review_plan(plan: SprintPlan) -> list[ReviewIssue]:
    issues: list[ReviewIssue] = []
    epic_ids = {epic.id for epic in plan.epics}
    story_ids = {story.id for story in plan.user_stories}
    task_ids = [task.id for task in plan.tasks]

    duplicate_epic_ids = sorted({
        epic.id for epic in plan.epics
        if sum(candidate.id == epic.id for candidate in plan.epics) > 1
    })
    for epic_id in duplicate_epic_ids:
        issues.append(ReviewIssue(
            code="DUPLICATE_EPIC_ID",
            severity=Severity.HIGH,
            description=f"Epic ID {epic_id} is duplicated.",
            affected_element=epic_id,
            suggested_correction="Assign a unique Epic ID.",
        ))

    duplicate_story_ids = sorted({
        story.id for story in plan.user_stories
        if sum(candidate.id == story.id for candidate in plan.user_stories) > 1
    })
    for story_id in duplicate_story_ids:
        issues.append(ReviewIssue(
            code="DUPLICATE_STORY_ID",
            severity=Severity.HIGH,
            description=f"User Story ID {story_id} is duplicated.",
            affected_element=story_id,
            suggested_correction="Assign a unique User Story ID.",
        ))

    duplicate_task_ids = sorted({
        task_id for task_id in task_ids if task_ids.count(task_id) > 1
    })
    for task_id in duplicate_task_ids:
        issues.append(ReviewIssue(
            code="DUPLICATE_TASK_ID",
            severity=Severity.HIGH,
            description=f"Task ID {task_id} is duplicated.",
            affected_element=task_id,
            suggested_correction="Assign a unique Task ID.",
        ))

    if not plan.epics:
        issues.append(ReviewIssue(
            code="NO_EPICS",
            severity=Severity.CRITICAL,
            description="The backlog has no Epics.",
            suggested_correction="Generate at least one Epic.",
        ))

    for story in plan.user_stories:
        if story.epic_id not in epic_ids:
            issues.append(ReviewIssue(
                code="INVALID_STORY_EPIC",
                severity=Severity.HIGH,
                description=f"Story {story.id} references a missing Epic.",
                affected_element=story.id,
            ))
        if not story.acceptance_criteria:
            issues.append(ReviewIssue(
                code="MISSING_ACCEPTANCE_CRITERIA",
                severity=Severity.HIGH,
                description=f"Story {story.id} has no Acceptance Criteria.",
                affected_element=story.id,
                suggested_correction="Add at least one testable criterion.",
            ))

    for task in plan.tasks:
        if task.user_story_id not in story_ids:
            issues.append(ReviewIssue(
                code="INVALID_TASK_STORY",
                severity=Severity.HIGH,
                description=f"Task {task.id} references a missing User Story.",
                affected_element=task.id,
            ))
        if task.estimate not in FIBONACCI_ESTIMATES:
            issues.append(ReviewIssue(
                code="INVALID_ESTIMATE",
                severity=Severity.HIGH,
                description=f"Task {task.id} has no valid Fibonacci estimate.",
                affected_element=task.id,
                suggested_correction="Estimate as 1, 2, 3, 5 or 8.",
            ))

    dependency_result = analyze_dependencies(plan.tasks, plan.dependencies)
    for error in dependency_result.errors:
        issues.append(ReviewIssue(
            code="DEPENDENCY_PROBLEM",
            severity=Severity.CRITICAL,
            description=error,
            suggested_correction="Remove invalid references or dependency cycles.",
        ))

    for sprint in plan.sprints:
        if sprint.workload > sprint.capacity:
            issues.append(ReviewIssue(
                code="SPRINT_CAPACITY_EXCEEDED",
                severity=Severity.HIGH,
                description=f"Sprint {sprint.number} exceeds capacity.",
                affected_element=f"Sprint {sprint.number}",
            ))

    for task_id in plan.unassigned_task_ids:
        issues.append(ReviewIssue(
            code="UNASSIGNED_TASK",
            severity=Severity.HIGH,
            description=f"Task {task_id} could not be assigned to a sprint.",
            affected_element=task_id,
        ))

    return issues


def save_approved_plan(plan: SprintPlan, approval: "Approval") -> bool:
    """Return whether a plan is eligible for persistence."""

    from sprintpilot.models import ApprovalStatus

    if approval.status != ApprovalStatus.APPROVED:
        raise ValueError("A plan can be saved only after explicit approval.")
    if approval.decided_at is None:
        raise ValueError("Approved plans must include a decision timestamp.")
    plan.approval.status = approval.status
    plan.approval.decided_at = approval.decided_at
    plan.approval.comment = approval.comment
    return True
