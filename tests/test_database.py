from sprintpilot.database import (
    create_tables,
    get_project,
    list_projects,
    save_project,
)


def test_project_round_trip() -> None:
    create_tables()
    record = save_project(
        name="Database Test",
        brief={"name": "Database Test", "description": "Test project"},
        analysis={"summary": "Test analysis"},
        plan={"project_id": "1"},
    )

    loaded = get_project(record.id)
    assert loaded is not None
    assert loaded.name == "Database Test"
    assert loaded.brief_json["description"] == "Test project"
    assert loaded.plan_json == {"project_id": "1"}


def test_project_list_contains_saved_project() -> None:
    create_tables()
    save_project(
        name="List Test",
        brief={"name": "List Test", "description": "Test project"},
    )

    names = [project.name for project in list_projects()]
    assert "List Test" in names
