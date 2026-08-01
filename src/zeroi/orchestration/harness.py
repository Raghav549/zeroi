import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from ..bus import (
    STREAM_APPROVALS,
    STREAM_API,
    STREAM_BROWSER,
    STREAM_CLI,
    STREAM_GUI,
    STREAM_PLAN,
    STREAM_REQUESTS,
    STREAM_SEARCH,
    STREAM_TASKS,
    STREAM_VERIFY,
    EventBus,
)
from ..db import SessionLocal
from ..ids import new_id
from ..models import PlanRecord, SessionRecord
from ..recovery import RecoveryEngine, RecoveryStrategy, classify_error
from ..schemas import (
    ApprovalDecided,
    ApprovalRequestModel,
    ExecutorType,
    Plan,
    PlanCompleted,
    PlanRequest,
    RequestCreated,
    RiskLevel,
    SessionState,
    SessionStatus,
    StepCompleted,
    StepExecutionRequest,
    StepStatus,
    Subtask,
    TaskStatus,
    VerificationCompleted,
    VerificationRequest,
    utcnow,
)
from ..security import PolicyEngine

log = logging.getLogger(__name__)


class CreateRequestBody(BaseModel):
    goal: str
    user_id: str | None = None
    context: dict[str, Any] = {}


EXECUTOR_STREAMS = {
    ExecutorType.GUI: STREAM_GUI,
    ExecutorType.CLI: STREAM_CLI,
    ExecutorType.BROWSER: STREAM_BROWSER,
    ExecutorType.API: STREAM_API,
    ExecutorType.DEEPSEARCH: STREAM_SEARCH,
}


class Harness:
    def __init__(self, bus: EventBus):
        self.bus = bus
        self.policy = PolicyEngine()
        self.recovery = RecoveryEngine()
        self.router = APIRouter()
        self._register_routes()

    def _register_routes(self) -> None:
        @self.router.post("/v1/requests")
        async def create_request(body: CreateRequestBody, _=Depends(self._auth_dependency())):
            session_id = await self.create_request(body.goal, body.user_id, body.context)
            return {"session_id": session_id}

        @self.router.get("/v1/sessions/{session_id}")
        async def get_session(session_id: str, _=Depends(self._auth_dependency())):
            async with SessionLocal() as db:
                rec = await db.get(SessionRecord, session_id)
                if not rec:
                    raise HTTPException(404, "session not found")
                return {
                    "id": rec.id,
                    "status": rec.status,
                    "goal": rec.goal,
                    "state": rec.state,
                }

    def _auth_dependency(self):
        from ..security import require_auth

        return require_auth

    async def create_request(self, goal: str, user_id: str | None, context: dict[str, Any]) -> str:
        session_id = new_id("sess")
        state = SessionState(id=session_id, user_id=user_id, goal=goal, context=context)

        async with SessionLocal() as db:
            db.add(
                SessionRecord(
                    id=session_id,
                    user_id=user_id,
                    goal=goal,
                    status=SessionStatus.PLANNING.value,
                    state=state.model_dump(mode="json"),
                )
            )
            await db.commit()

        await self.bus.publish(
            STREAM_REQUESTS,
            "request.created",
            RequestCreated(session_id=session_id, user_id=user_id, goal=goal, context=context),
        )
        return session_id

    async def handle_requests(self, envelope: dict[str, Any]) -> None:
        if envelope.get("type") != "request.created":
            return

        payload = RequestCreated.model_validate(envelope["payload"])
        await self.bus.publish(
            STREAM_PLAN,
            "plan.requested",
            PlanRequest(session_id=payload.session_id, goal=payload.goal, context=payload.context),
        )

    async def handle_plan(self, envelope: dict[str, Any]) -> None:
        if envelope.get("type") != "plan.completed":
            return

        payload = PlanCompleted.model_validate(envelope["payload"])
        plan = payload.plan

        async with SessionLocal() as db:
            existing = await db.execute(select(PlanRecord).where(PlanRecord.id == plan.id))
            plan_rec = existing.scalar_one_or_none()

            if plan_rec:
                plan_rec.plan = plan.model_dump(mode="json")
                flag_modified(plan_rec, "plan")
            else:
                plan_rec = PlanRecord(
                    id=plan.id,
                    session_id=plan.session_id,
                    plan=plan.model_dump(mode="json"),
                    active=True,
                )
                db.add(plan_rec)

            session = await db.get(SessionRecord, plan.session_id)
            if session:
                session.status = SessionStatus.RUNNING.value
                state = session.state or {}
                state["plan_id"] = plan.id
                state["updated_at"] = utcnow()
                session.state = state
                flag_modified(session, "state")

            await db.commit()

        await self.schedule_ready_tasks(plan.session_id, plan.id)

    async def handle_task_events(self, envelope: dict[str, Any]) -> None:
        etype = envelope.get("type")
        payload = envelope.get("payload", {})

        if etype == "step.completed":
            await self.on_step_completed(StepCompleted.model_validate(payload))
        elif etype == "step.failed":
            await self.on_step_failed(StepCompleted.model_validate(payload))
        elif etype == "verification.completed":
            await self.on_verification_completed(VerificationCompleted.model_validate(payload))

    async def handle_approvals(self, envelope: dict[str, Any]) -> None:
        if envelope.get("type") != "approval.decided":
            return

        decision = ApprovalDecided.model_validate(envelope["payload"])
        async with SessionLocal() as db:
            from ..models import ApprovalRecord

            approval = await db.get(ApprovalRecord, decision.id)
            if not approval:
                return

            session = await db.get(SessionRecord, approval.session_id)
            if not session:
                return

            plan_id = (session.state or {}).get("plan_id")
            if not plan_id:
                return

            plan_rec = await db.get(PlanRecord, plan_id)
            if not plan_rec:
                return

            plan = Plan.model_validate(plan_rec.plan)
            for task in plan.tasks:
                if task.id == approval.task_id:
                    if decision.approved:
                        task.inputs["approved"] = True
                        task.status = TaskStatus.PENDING
                    else:
                        task.status = TaskStatus.FAILED
                        task.error = f"Approval rejected: {decision.reason or 'no reason'}"

            plan_rec.plan = plan.model_dump(mode="json")
            flag_modified(plan_rec, "plan")
            await db.commit()

            if decision.approved and approval.task_id:
                await self.schedule_ready_tasks(plan.session_id, plan.id)
            else:
                await self.maybe_finalize_session(plan.session_id, plan.id)

    async def schedule_ready_tasks(self, session_id: str, plan_id: str) -> None:
        async with SessionLocal() as db:
            plan_rec = await db.get(PlanRecord, plan_id)
            if not plan_rec:
                return

            plan = Plan.model_validate(plan_rec.plan)
            statuses = {t.id: t.status for t in plan.tasks}
            changed = False

            for task in plan.tasks:
                if task.status not in {TaskStatus.PENDING, TaskStatus.READY}:
                    continue

                deps_done = all(
                    statuses.get(dep) in {TaskStatus.COMPLETED, TaskStatus.VERIFIED}
                    for dep in task.dependencies
                )
                if not deps_done:
                    continue

                await self.dispatch_task(db, plan, task)
                changed = True

            if changed:
                plan_rec.plan = plan.model_dump(mode="json")
                flag_modified(plan_rec, "plan")
                await db.commit()

        await self.maybe_finalize_session(session_id, plan_id)

    async def dispatch_task(self, db, plan: Plan, task: Subtask) -> None:
        risk = self.policy.classify(task.model_dump())
        if risk in {RiskLevel.HIGH, RiskLevel.IRREVERSIBLE} and not task.inputs.get("approved"):
            task.status = TaskStatus.WAITING_CONFIRMATION
            approval = ApprovalRequestModel(
                session_id=plan.session_id,
                task_id=task.id,
                risk=risk,
                title=f"Approve {task.title}",
                details={"goal": task.goal, "executor": task.executor.value, "steps": [s.model_dump() for s in task.steps]},
            )

            from ..models import ApprovalRecord

            db.add(
                ApprovalRecord(
                    id=approval.id,
                    session_id=approval.session_id,
                    task_id=approval.task_id,
                    risk=approval.risk.value,
                    title=approval.title,
                    details=approval.details,
                    status="PENDING",
                )
            )
            await self.bus.publish(STREAM_APPROVALS, "approval.requested", approval)
            return

        task.status = TaskStatus.RUNNING
        await self.dispatch_current_step(plan, task)

    async def dispatch_current_step(self, plan: Plan, task: Subtask) -> None:
        if task.current_step >= len(task.steps):
            task.status = TaskStatus.COMPLETED
            return

        step = task.steps[task.current_step]
        step.status = StepStatus.RUNNING

        stream = EXECUTOR_STREAMS.get(step.executor)
        if not stream:
            step.status = StepStatus.FAILED
            step.error = f"No executor stream for {step.executor}"
            task.status = TaskStatus.FAILED
            return

        req = StepExecutionRequest(
            session_id=plan.session_id,
            task_id=task.id,
            step_id=step.id,
            executor=step.executor,
            kind=step.kind,
            payload=step.payload,
            context=plan.context,
        )
        await self.bus.publish(stream, "step.execution.requested", req)

    async def on_step_completed(self, payload: StepCompleted) -> None:
        async with SessionLocal() as db:
            ctx = await self._load_plan_context(db, payload.session_id)
            if not ctx:
                return

            plan_rec, plan, task = ctx
            step = next((s for s in task.steps if s.id == payload.step_id), None)
            if not step:
                return

            step.status = StepStatus.COMPLETED
            step.result = payload.result
            task.artifacts.extend(payload.artifacts)
            task.observations.extend(payload.observations)
            task.outputs.update(payload.result)

            if task.current_step + 1 < len(task.steps):
                task.current_step += 1
                await self.dispatch_current_step(plan, task)
            else:
                task.status = TaskStatus.COMPLETED
                task.result = self._merge_task_result(task)
                await self.bus.publish(
                    STREAM_VERIFY,
                    "verification.requested",
                    VerificationRequest(
                        session_id=plan.session_id,
                        plan_id=plan.id,
                        task_id=task.id,
                        outputs=task.outputs,
                    ),
                )

            plan_rec.plan = plan.model_dump(mode="json")
            flag_modified(plan_rec, "plan")
            await db.commit()

        await self.schedule_ready_tasks(payload.session_id, plan.id)

    async def on_step_failed(self, payload: StepCompleted) -> None:
        async with SessionLocal() as db:
            ctx = await self._load_plan_context(db, payload.session_id)
            if not ctx:
                return

            plan_rec, plan, task = ctx
            step = next((s for s in task.steps if s.id == payload.step_id), None)
            if not step:
                return

            step.status = StepStatus.FAILED
            step.error = payload.error
            task.attempts += 1
            task.error = payload.error

            category = classify_error(payload.error or "", task)
            strategy, hint = self.recovery.decide(category, task.attempts)

            if strategy == RecoveryStrategy.RETRY and task.attempts < task.max_attempts:
                step.payload["recovery_hint"] = hint
                step.payload["failure_category"] = category.value
                step.status = StepStatus.PENDING
                await self.dispatch_current_step(plan, task)

            elif strategy == RecoveryStrategy.SWITCH_EXECUTOR:
                if step.executor == ExecutorType.GUI:
                    step.executor = ExecutorType.CLI
                    step.kind = "CLI_COMMAND"
                    step.payload = {
                        "command": ["echo", f"Fallback for {task.goal}"],
                        "recovery_hint": hint,
                    }
                step.status = StepStatus.PENDING
                await self.dispatch_current_step(plan, task)

            elif strategy == RecoveryStrategy.REPLAN:
                task.status = TaskStatus.REPLANNING
                await self.bus.publish(
                    STREAM_PLAN,
                    "plan.replan.requested",
                    PlanRequest(
                        session_id=plan.session_id,
                        goal=plan.goal,
                        context=plan.context,
                        current_plan=plan.model_dump(mode="json"),
                        failed_task=task.model_dump(mode="json"),
                        error=payload.error,
                        replan=True,
                    ),
                )

            elif strategy == RecoveryStrategy.REQUEST_HUMAN:
                task.status = TaskStatus.WAITING_CONFIRMATION
                approval = ApprovalRequestModel(
                    session_id=plan.session_id,
                    task_id=task.id,
                    step_id=step.id,
                    risk=RiskLevel.HIGH,
                    title="Recovery assistance required",
                    details={"error": payload.error, "hint": hint, "category": category.value},
                )
                from ..models import ApprovalRecord

                db.add(
                    ApprovalRecord(
                        id=approval.id,
                        session_id=approval.session_id,
                        task_id=approval.task_id,
                        step_id=approval.step_id,
                        risk=approval.risk.value,
                        title=approval.title,
                        details=approval.details,
                        status="PENDING",
                    )
                )
                await self.bus.publish(STREAM_APPROVALS, "approval.requested", approval)

            else:
                task.status = TaskStatus.FAILED

            plan_rec.plan = plan.model_dump(mode="json")
            flag_modified(plan_rec, "plan")
            await db.commit()

        await self.maybe_finalize_session(payload.session_id, plan.id)

    async def on_verification_completed(self, payload: VerificationCompleted) -> None:
        async with SessionLocal() as db:
            ctx = await self._load_plan_context(db, payload.session_id)
            if not ctx:
                return

            plan_rec, plan, task = ctx

            if payload.passed:
                task.status = TaskStatus.VERIFIED
                task.outputs["verification"] = payload.details
            else:
                task.status = TaskStatus.FAILED
                task.error = f"Verification failed: {payload.details}"

            plan_rec.plan = plan.model_dump(mode="json")
            flag_modified(plan_rec, "plan")
            await db.commit()

        if payload.passed:
            await self.schedule_ready_tasks(payload.session_id, payload.plan_id)
        await self.maybe_finalize_session(payload.session_id, payload.plan_id)

    async def maybe_finalize_session(self, session_id: str, plan_id: str) -> None:
        async with SessionLocal() as db:
            plan_rec = await db.get(PlanRecord, plan_id)
            session = await db.get(SessionRecord, session_id)
            if not plan_rec or not session:
                return

            plan = Plan.model_validate(plan_rec.plan)
            terminal = {TaskStatus.VERIFIED, TaskStatus.FAILED, TaskStatus.CANCELLED}
            if any(t.status not in terminal for t in plan.tasks):
                return

            failed = [t for t in plan.tasks if t.status != TaskStatus.VERIFIED]
            status = SessionStatus.FAILED if failed else SessionStatus.COMPLETED

            session.status = status.value
            state = session.state or {}
            state["final_response"] = {
                "status": status.value,
                "results": {t.id: t.result for t in plan.tasks},
                "failed": [t.id for t in failed],
                "artifacts": [a for t in plan.tasks for a in t.artifacts],
            }
            state["updated_at"] = utcnow()
            session.state = state
            flag_modified(session, "state")
            await db.commit()

    async def _load_plan_context(self, db, session_id: str):
        session = await db.get(SessionRecord, session_id)
        if not session:
            return None

        plan_id = (session.state or {}).get("plan_id")
        if not plan_id:
            return None

        plan_rec = await db.get(PlanRecord, plan_id)
        if not plan_rec:
            return None

        return plan_rec, Plan.model_validate(plan_rec.plan), None

    async def _load_plan_context(self, db, session_id: str):
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

        # This helper is used by step events where task_id is in payload.
        # Caller replaces third item.
        return plan_rec, plan, None

    async def _load_plan_context(self, db, session_id: str):
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
        return plan_rec, plan, None

    def _merge_task_result(self, task: Subtask) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        for idx, step in enumerate(task.steps):
            merged[f"step_{idx}_{step.executor.value}"] = step.result or {}
        merged["artifacts"] = task.artifacts
        return merged
