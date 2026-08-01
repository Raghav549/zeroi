from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from ..models import PlanRecord, SessionRecord
from ..schemas import Plan, Subtask


async def load_session(db: AsyncSession, session_id: str) -> Optional[SessionRecord]:
    return await db.get(SessionRecord, session_id)


async def load_plan(
    db: AsyncSession,
    session_id: str,
) -> Optional[tuple[SessionRecord, PlanRecord, Plan]]:
    session = await db.get(SessionRecord, session_id)
    if not session:
        return None

    plan_id = (session.state or {}).get("plan_id")
    if not plan_id:
        return None

    plan_rec = await db.get(PlanRecord, plan_id)
    if not plan_rec:
        return None

    plan = Plan.model_validate(plan_rec.plan)
    return session, plan_rec, plan


async def load_plan_task(
    db: AsyncSession,
    session_id: str,
    task_id: str,
) -> Optional[tuple[SessionRecord, PlanRecord, Plan, Subtask]]:
    loaded = await load_plan(db, session_id)
    if not loaded:
        return None

    session, plan_rec, plan = loaded
    task = next((t for t in plan.tasks if t.id == task_id), None)
    if not task:
        return None

    return session, plan_rec, plan, task


async def save_plan(db: AsyncSession, plan_rec: PlanRecord, plan: Plan) -> None:
    plan_rec.plan = plan.model_dump(mode="json")
    flag_modified(plan_rec, "plan")
    await db.commit()
