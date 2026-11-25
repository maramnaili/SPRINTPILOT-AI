from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse

from sprintpilot.database import (
    create_tables,
    get_project as fetch_project,
    list_projects,
    save_project,
)
from sprintpilot.knowledge import (
    list_guideline_sources,
    retrieve_project_guidelines,
    upload_guideline,
)
from sprintpilot.models import Approval, ProjectBrief, SprintPlan
from sprintpilot.backlog import generate_backlog
from sprintpilot.analysis import analyze_project_brief
from sprintpilot.planning import (
    assign_sprints,
    calculate_sprint_capacity,
    estimate_task_effort,
    review_plan,
    save_approved_plan,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    from pathlib import Path
    knowledge_directory = Path("data") / "knowledge_base"
    for guideline_path in knowledge_directory.glob("*"):
        if guideline_path.suffix.lower() in {".txt", ".md"}:
            try:
                upload_guideline(guideline_path.name, guideline_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, ValueError):
                pass
    yield


app = FastAPI(
    title="SprintPilot AI",
    version="0.1.0",
    description="Structured AI-assisted software project planning",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/projects", status_code=201)
def create_project(brief: ProjectBrief) -> dict:
    record = save_project(
        name=brief.name,
        brief=brief.model_dump(mode="json"),
    )
    return {
        "id": record.id,
        "name": record.name,
        "approval_status": record.approval_status,
    }


@app.get("/projects")
def projects() -> list[dict]:
    return [
        {
            "id": record.id,
            "name": record.name,
            "approval_status": record.approval_status,
        }
        for record in list_projects()
    ]


@app.get("/projects/{project_id}")
def get_project(project_id: int) -> dict:
    record = fetch_project(project_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return {
        "id": record.id,
        "name": record.name,
        "brief": record.brief_json,
        "analysis": record.analysis_json,
        "plan": record.plan_json,
        "approval_status": record.approval_status,
    }


@app.post("/projects/{project_id}/generate")
def generate_project(project_id: int) -> dict:
    record = fetch_project(project_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Project not found.")

    try:
        brief = ProjectBrief.model_validate(record.brief_json)
        analysis = analyze_project_brief(brief)
        guidelines = retrieve_project_guidelines(
            f"{brief.name} {brief.description} {' '.join(brief.features)}",
            max_results=3,
        )
        backlog = generate_backlog(brief, analysis, guidelines=guidelines)
        for task in backlog.tasks:
            estimate, reason = estimate_task_effort(task)
            task.estimate = estimate

        plan = SprintPlan(
            project_id=str(project_id),
            analysis=analysis,
            epics=backlog.epics,
            user_stories=backlog.user_stories,
            tasks=backlog.tasks,
        )
        plan.guideline_sources = sorted({
            guideline.source for guideline in guidelines
        })

        capacity = calculate_sprint_capacity(
            brief.sprint_capacity,
            brief.duration_weeks,
            capacity_unit=brief.capacity_unit,
        )
        plan.sprints, plan.unassigned_task_ids = assign_sprints(
            plan.tasks,
            plan.dependencies,
            brief.sprint_capacity,
            len(capacity),
        )
        plan.review_issues = review_plan(plan)
        save_project(
            name=record.name,
            brief=record.brief_json,
            analysis=analysis.model_dump(mode="json"),
            plan=plan.model_dump(mode="json"),
            project_id=project_id,
        )
        return plan.model_dump(mode="json")
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/projects/{project_id}/plan")
def get_plan(project_id: int) -> dict:
    record = fetch_project(project_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    if record.plan_json is None:
        raise HTTPException(status_code=404, detail="Plan not generated.")
    return record.plan_json


@app.put("/projects/{project_id}/plan")
def update_plan(project_id: int, plan: SprintPlan) -> dict:
    record = fetch_project(project_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    if plan.approval.status.value != "pending":
        raise HTTPException(
            status_code=400,
            detail="Approval cannot be set through plan editing.",
        )
    plan.review_issues = review_plan(plan)
    save_project(
        name=record.name,
        brief=record.brief_json,
        analysis=record.analysis_json,
        plan=plan.model_dump(mode="json"),
        project_id=project_id,
    )
    return plan.model_dump(mode="json")


@app.post("/projects/{project_id}/approve")
def approve_project(project_id: int, approval: Approval) -> dict:
    record = fetch_project(project_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    if record.plan_json is None:
        raise HTTPException(status_code=404, detail="Plan not generated.")

    plan = SprintPlan.model_validate(record.plan_json)
    try:
        if approval.status.value == "approved":
            save_approved_plan(plan, approval)
        elif approval.status.value == "rejected":
            if approval.decided_at is None:
                raise ValueError("Rejected plans must include a decision timestamp.")
            plan.approval.status = approval.status
            plan.approval.decided_at = approval.decided_at
            plan.approval.comment = approval.comment
        else:
            raise ValueError("Approval decision must be approved or rejected.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    save_project(
        name=record.name,
        brief=record.brief_json,
        analysis=record.analysis_json,
        plan=plan.model_dump(mode="json"),
        approval_status=approval.status.value,
        project_id=project_id,
    )
    return {"project_id": project_id, "approval": approval.model_dump(mode="json")}


@app.get("/projects/{project_id}/export")
def export_project(project_id: int) -> JSONResponse:
    record = fetch_project(project_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    if record.plan_json is None:
        raise HTTPException(status_code=404, detail="Plan not generated.")

    plan = SprintPlan.model_validate(record.plan_json)
    return JSONResponse(
        content=plan.model_dump(mode="json"),
        headers={
            "Content-Disposition": f'attachment; filename="sprintpilot_project_{project_id}.json"',
        },
    )


@app.get("/knowledge")
def knowledge_sources() -> dict:
    return {"sources": list_guideline_sources()}


@app.post("/knowledge/upload")
async def upload_knowledge(file: UploadFile = File(...)) -> dict:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required.")
    if not file.filename.lower().endswith((".txt", ".md")):
        raise HTTPException(status_code=400, detail="Only TXT and Markdown files are supported.")

    content = await file.read()
    if len(content) > 1_000_000:
        raise HTTPException(status_code=413, detail="Knowledge file is too large.")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="Knowledge file must be UTF-8 text.") from exc

    try:
        chunk_count = upload_guideline(file.filename, text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"source": file.filename, "chunks": chunk_count}
