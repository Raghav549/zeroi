import uuid

import pytest

from zeroi.db import SessionLocal, init_db
from zeroi.models import PlanRecord, SessionRecord
from zeroi.orchestration.state import load_plan_task, save_plan
from zeroi.schemas import ExecutorType, Plan, Subtask


@pytest.mark.asyncio
async def test_load_plan_task():
    await init_db()

    session_id = f"sess_{uuid.uuid4().hex[:12]}"
    plan_id = f"plan_{uuid.uuid4().hex[:12]}"
    task_id = f"task_{uuid.uuid4().hex[:12]}"

    plan = Plan(
        id=plan_id,
        session_id=session_id,
        goal="test goal",
        tasks=[
            Subtask(
                id=task_id,
                title="test task",
                goal="test task goal",
                executor=ExecutorType.CLI,
            )
        ],
    )

    async with SessionLocal() as db:
        db.add(
            SessionRecord(
                id=session_id,
                goal="test goal",
                status="RUNNING",
                state={"plan_id": plan_id},
            )
        )
        db.add(
            PlanRecord(
                id=plan_id,
                session_id=session_id,
                plan=plan.model_dump(mode="json"),
                active=True,
            )
        )
        await db.commit()

    async with SessionLocal() as db:
        loaded = await load_plan_task(db, session_id, task_id)
        assert loaded is not None

        _, _, loaded_plan, loaded_task = loaded
        assert loaded_plan.id == plan_id
        assert loaded_task.id == task_id


@pytest.mark.asyncio
async def test_save_plan_updates_json():
    await init_db()

    session_id = f"sess_{uuid.uuid4().hex[:12]}"
    plan_id = f"plan_{uuid.uuid4().hex[:12]}"
    task_id = f"task_{uuid.uuid4().hex[:12]}"

    plan = Plan(
        id=plan_id,
        session_id=session_id,
        goal="save test",
        tasks=[
            Subtask(
                id=task_id,
                title="task",
                goal="goal",
                executor=ExecutorType.CLI,
            )
        ],
    )

    async with SessionLocal() as db:
        db.add(
            SessionRecord(
                id=session_id,
                goal="save test",
                status="RUNNING",
                state={"plan_id": plan_id},
            )
        )
        db.add(
            PlanRecord(
                id=plan_id,
                session_id=session_id,
                plan=plan.model_dump(mode="json"),
                active=True,
            )
        )
        await db.commit()

    async with SessionLocal() as db:
        loaded = await load_plan_task(db, session_id, task_id)
        assert loaded is not None

        _, plan_rec, loaded_plan, task = loaded
        print("Loaded plan task:", loaded_plan.tasks[0].title)

        task.title = "updated title"

        print("Task object:", task.title)
        print("Loaded plan task:", loaded_plan.tasks[0].title)
        print("Same object:", task is loaded_plan.tasks[0])

        await save_plan(db, plan_rec, loaded_plan)