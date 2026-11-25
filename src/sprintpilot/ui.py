import os
from datetime import datetime, timezone

import httpx
import streamlit as st
from pydantic import ValidationError

from sprintpilot.models import SprintPlan


API_URL = os.getenv("SPRINTPILOT_API_URL", "http://127.0.0.1:8000")


def api(method: str, path: str, *, timeout: float = 30, **kwargs):
    try:
        response = httpx.request(
            method,
            f"{API_URL}{path}",
            timeout=timeout,
            **kwargs,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json().get("detail", exc.response.text)
        except Exception:
            detail = exc.response.text
        st.error(detail)
    except httpx.TimeoutException:
        st.error(
            "The backend request timed out. Check whether the plan was generated "
            "before retrying."
        )
    except httpx.RequestError as exc:
        st.error(f"Backend unavailable: {exc}")
    return None


st.set_page_config(page_title="SprintPilot AI", layout="wide")
st.title("SprintPilot AI")

page = st.sidebar.radio(
    "Navigation",
    ["Home", "Create Project", "Planning Results", "Knowledge Base"],
)

if page == "Home":
    st.subheader("Software project planning assistant")
    st.write(
        "Transform a project brief into a structured backlog and proposed sprint plan."
    )
    health = api("GET", "/health")
    if health:
        st.success("Backend is online")

    projects = api("GET", "/projects") or []
    st.subheader("Existing projects")
    if projects:
        for project in projects:
            st.write(
                f"#{project['id']} - {project['name']} "
                f"({project['approval_status']})"
            )
    else:
        st.info("No projects created yet.")

elif page == "Create Project":
    st.subheader("Create project")
    name = st.text_input("Project name")
    description = st.text_area("Description")
    goals = st.text_area("Goals (one per line)")
    features = st.text_area("Features (one per line)")
    constraints = st.text_area("Constraints (one per line)")
    team_size = st.number_input("Team size", 1, 100, 3)
    duration_weeks = st.number_input("Duration (weeks)", 1, 520, 6)
    sprint_capacity = st.number_input("Sprint capacity", 1.0, 1000.0, 20.0)
    capacity_unit = st.selectbox("Capacity unit", ["points", "hours"])
    notes = st.text_area("Additional notes")

    if st.button("Create and generate"):
        if not name.strip() or not description.strip():
            st.warning("Name and description are required.")
        else:
            brief = {
                "name": name,
                "description": description,
                "goals": [item.strip() for item in goals.splitlines() if item.strip()],
                "features": [item.strip() for item in features.splitlines() if item.strip()],
                "constraints": [item.strip() for item in constraints.splitlines() if item.strip()],
                "team_size": team_size,
                "duration_weeks": duration_weeks,
                "sprint_capacity": sprint_capacity,
                "capacity_unit": capacity_unit,
                "additional_notes": notes,
            }
            project = api("POST", "/projects", json=brief)
            if project:
                st.session_state["selected_project_id"] = project["id"]
                st.success(f"Created project #{project['id']}")
                with st.spinner("Generating the plan. This may take a few minutes..."):
                    plan = api(
                        "POST",
                        f"/projects/{project['id']}/generate",
                        timeout=660,
                    )
                if plan:
                    st.success("Plan generated.")
                    st.json(plan)

elif page == "Planning Results":
    st.subheader("Planning results")
    projects = api("GET", "/projects") or []
    if not projects:
        st.info("Create a project first.")
    else:
        project_labels = {
            f"#{project['id']} - {project['name']}": project["id"]
            for project in projects
        }
        selected_label = st.selectbox("Project", list(project_labels))
        project_id = project_labels[selected_label]
        plan = api("GET", f"/projects/{project_id}/plan")
        if plan is None:
            st.info("This project does not have a generated plan yet.")
            if st.button("Generate plan", key=f"generate_plan_{project_id}"):
                with st.spinner("Generating the plan. This may take a few minutes..."):
                    generated_plan = api(
                        "POST",
                        f"/projects/{project_id}/generate",
                        timeout=660,
                    )
                if generated_plan:
                    st.success("Plan generated.")
                    st.rerun()

        if plan is not None:
            try:
                plan = SprintPlan.model_validate(plan).model_dump(mode="json")
            except ValidationError:
                st.warning(
                    "This project has an incomplete or invalid saved plan. "
                    "Regenerate it to view planning results."
                )
                if st.button(
                    "Regenerate plan",
                    key=f"regenerate_plan_{project_id}",
                ):
                    regenerated_plan = api(
                        "POST",
                        f"/projects/{project_id}/generate",
                        timeout=660,
                    )
                    if regenerated_plan:
                        st.success("Plan regenerated.")
                        st.rerun()
                plan = None

        if plan is not None:
            tab_epics, tab_sprints, tab_review = st.tabs(
                ["Backlog", "Sprints", "Review"]
            )
            with tab_epics:
                st.json({
                    "epics": plan["epics"],
                    "user_stories": plan["user_stories"],
                    "tasks": plan["tasks"],
                })
            with tab_sprints:
                st.json({
                    "sprints": plan["sprints"],
                    "unassigned_task_ids": plan["unassigned_task_ids"],
                })
            with tab_review:
                st.json(plan["review_issues"])

            st.subheader("Edit plan")
            edited_json = st.text_area(
                "Edited plan JSON",
                value=__import__("json").dumps(plan, indent=2),
                height=300,
            )
            if st.button("Save plan edits"):
                try:
                    edited_plan = __import__("json").loads(edited_json)
                    saved = api(
                        "PUT",
                        f"/projects/{project_id}/plan",
                        json=edited_plan,
                    )
                    if saved:
                        st.success("Plan edits saved.")
                except __import__("json").JSONDecodeError as exc:
                    st.error(f"Invalid JSON: {exc}")

            if st.button("Approve plan"):
                approval = api(
                    "POST",
                    f"/projects/{project_id}/approve",
                    json={
                        "status": "approved",
                        "decided_at": datetime.now(timezone.utc).isoformat(),
                        "comment": "Approved from Streamlit",
                    },
                )
                if approval:
                    st.success("Plan approved.")

            if st.button("Reject plan"):
                approval = api(
                    "POST",
                    f"/projects/{project_id}/approve",
                    json={
                        "status": "rejected",
                        "decided_at": datetime.now(timezone.utc).isoformat(),
                        "comment": "Rejected from Streamlit",
                    },
                )
                if approval:
                    st.warning("Plan rejected.")

            if st.button("Export plan as JSON"):
                st.download_button(
                    "Download JSON",
                    data=__import__("json").dumps(plan, indent=2),
                    file_name=f"sprintpilot_project_{project_id}.json",
                    mime="application/json",
                )

elif page == "Knowledge Base":
    st.subheader("Knowledge base")
    source_list = api("GET", "/knowledge")
    if source_list:
        sources = source_list["sources"]
        if sources:
            st.write("Indexed sources:")
            for source in sources:
                st.write(f"- {source}")
        else:
            st.info("No guideline documents indexed yet.")
    uploaded = st.file_uploader(
        "Upload project-planning guideline",
        type=["txt", "md"],
    )
    if uploaded is not None and st.button("Add guideline"):
        result = api(
            "POST",
            "/knowledge/upload",
            files={"file": (uploaded.name, uploaded.getvalue())},
        )
        if result:
            st.success(
                f"Added {uploaded.name} with {result['chunks']} chunks."
            )
