import json
from pathlib import Path

from sprintpilot.models import ProjectBrief
from sprintpilot.planning import (
    analyze_dependencies,
    assign_sprints,
    calculate_sprint_capacity,
)


def evaluate_briefs(path: Path) -> dict:
    briefs = json.loads(path.read_text(encoding="utf-8"))
    valid_briefs = 0
    capacity_plans = 0

    for item in briefs:
        brief = ProjectBrief.model_validate(item)
        valid_briefs += 1
        capacities = calculate_sprint_capacity(
            brief.sprint_capacity,
            brief.duration_weeks,
            capacity_unit=brief.capacity_unit,
        )
        if capacities:
            capacity_plans += 1

    count = len(briefs)
    return {
        "brief_count": count,
        "schema_valid_briefs": valid_briefs,
        "schema_valid_rate": valid_briefs / count if count else 0,
        "capacity_plan_count": capacity_plans,
    }


if __name__ == "__main__":
    dataset = Path(__file__).parent / "example_briefs.json"
    metrics = evaluate_briefs(dataset)
    print(json.dumps(metrics, indent=2))
