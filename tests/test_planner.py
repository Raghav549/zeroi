import pytest

from zeroi.planner.engine import PlannerEngine


@pytest.mark.asyncio
async def test_heuristic_plan_includes_search():
    engine = PlannerEngine()
    plan = await engine.create_plan("sess_1", "Research Qwen-UI-Agent and summarize", {})

    assert plan.tasks
    assert any(t.executor.value == "DEEPSEARCH" for t in plan.tasks)


@pytest.mark.asyncio
async def test_plan_dependencies_are_valid():
    engine = PlannerEngine()
    plan = await engine.create_plan("sess_2", "Find file and convert image using app", {})

    ids = {t.id for t in plan.tasks}
    for task in plan.tasks:
        for dep in task.dependencies:
            assert dep in ids
