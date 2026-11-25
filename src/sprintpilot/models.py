from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProjectBrief(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)
    goals: list[str] = Field(default_factory=list)
    features: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    team_size: int = Field(default=1, ge=1, le=100)
    duration_weeks: int = Field(default=4, ge=1, le=520)
    sprint_capacity: float = Field(default=20.0, gt=0)
    capacity_unit: Literal["points", "hours"] = "points"
    additional_notes: str = ""


class ProjectAnalysis(StrictModel):
    summary: str = Field(min_length=1)
    goals: list[str] = Field(default_factory=list)
    features: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    clarification_questions: list[str] = Field(default_factory=list)


class Epic(StrictModel):
    id: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)


class UserStory(StrictModel):
    id: str = Field(min_length=1, max_length=50)
    epic_id: str = Field(min_length=1, max_length=50)
    text: str = Field(min_length=10)
    priority: Priority = Priority.MEDIUM
    acceptance_criteria: list[str] = Field(min_length=1)


class Task(StrictModel):
    id: str = Field(min_length=1, max_length=50)
    user_story_id: str = Field(min_length=1, max_length=50)
    description: str = Field(min_length=1)
    estimate: Literal[1, 2, 3, 5, 8] | None = None
    priority: Priority = Priority.MEDIUM
    status: TaskStatus = TaskStatus.TODO


class TaskDependency(StrictModel):
    task_id: str = Field(min_length=1, max_length=50)
    depends_on_task_id: str = Field(min_length=1, max_length=50)


class Sprint(StrictModel):
    number: int = Field(ge=1)
    capacity: float = Field(gt=0)
    capacity_unit: Literal["points", "hours"] = "points"
    task_ids: list[str] = Field(default_factory=list)
    workload: float = Field(default=0, ge=0)
    warnings: list[str] = Field(default_factory=list)


class ReviewIssue(StrictModel):
    code: str = Field(min_length=1, max_length=100)
    severity: Severity
    description: str = Field(min_length=1)
    affected_element: str = ""
    suggested_correction: str = ""


class Approval(StrictModel):
    status: ApprovalStatus = ApprovalStatus.PENDING
    decided_at: datetime | None = None
    comment: str = ""


class AgentRun(StrictModel):
    run_id: str = Field(min_length=1)
    current_phase: str = Field(min_length=1)
    status: Literal["running", "completed", "failed", "waiting_for_approval"] = "running"
    errors: list[str] = Field(default_factory=list)
    correction_attempts: int = Field(default=0, ge=0, le=2)


class SprintPlan(StrictModel):
    project_id: str = Field(min_length=1)
    analysis: ProjectAnalysis
    epics: list[Epic] = Field(default_factory=list)
    user_stories: list[UserStory] = Field(default_factory=list)
    tasks: list[Task] = Field(default_factory=list)
    dependencies: list[TaskDependency] = Field(default_factory=list)
    sprints: list[Sprint] = Field(default_factory=list)
    unassigned_task_ids: list[str] = Field(default_factory=list)
    review_issues: list[ReviewIssue] = Field(default_factory=list)
    approval: Approval = Field(default_factory=Approval)
    guideline_sources: list[str] = Field(default_factory=list)


class BacklogGenerationResult(StrictModel):
    epics: list[Epic] = Field(default_factory=list)
    user_stories: list[UserStory] = Field(default_factory=list)
    tasks: list[Task] = Field(default_factory=list)
