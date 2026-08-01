import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

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
from ..models import ApprovalRecord, PlanRecord, SessionRecord
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
    StepKind,
    StepStatus,
    Subtask,
    TaskStatus,
    VerificationCompleted,
    VerificationRequest,
    utcnow,
)
from ..security import PolicyEngine, require_auth
from .state import load_plan, load_plan_task, save_plan

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
        async def create_request(body: CreateRequestBody, _=Depends(require_auth)):
            session_id = await self.create_request(body.goal, body.user_id, body.context)
            return {"session_id": session_id}

        @self.router.get("/v1/sessions/{session_id}")
        async def get_session(session_id: str, _=Depends(require_auth)):
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
            plan_rec = await db.get(PlanRecord, plan.id)

            if plan_rec:
                plan_rec.plan = plan.model_dump(mode="json")
                plan_rec.active = True
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

            from sqlalchemy.orm.attributes import flag_modified

            if session:
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
            approval = await db.get(ApprovalRecord, decision.id)
            if not approval:
                return

            if not approval.task_id:
                return

            loaded = await load_plan_task(db, approval.session_id, approval.task_id)
            if not loaded:
                return

            session, plan_rec, plan, task = loaded

            if decision.approved:
                task.inputs["approved"] = True
                task.status = TaskStatus.PENDING
            else:
                task.status = TaskStatus.FAILED
                task.error = f"Approval rejected: {decision.reason or 'no reason'}"

            await save_plan(db, plan_rec, plan)

        if decision.approved:
            await self.schedule_ready_tasks(approval.session_id, plan.id)
        else:
            await self.maybe_finalize_session(approval.session_id, plan.id)

    async def schedule_ready_tasks(self, session_id: str, plan_id: str) -> None:
        async with SessionLocal() as db:
            loaded = await load_plan(db, session_id)
            if not loaded:
                return

            session, plan_rec, plan = loaded
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
                await save_plan(db, plan_rec, plan)

        await self.maybe_finalize_session(session_id, plan_id)

    async def dispatch_task(self, db, plan: Plan, task: Subtask) -> None:
        policy_risk = self.policy.classify(task.model_dump())
        risk = task.risk if task.risk != RiskLevel.LOW else policy_risk

        if self.policy.requires_approval(risk) and not task.inputs.get("approved"):
            task.status = TaskStatus.WAITING_CONFIRMATION

            approval = ApprovalRequestModel(
                session_id=plan.session_id,
                task_id=task.id,
                risk=risk,
                title=f"Approve {task.title}",
                details={
                    "goal": task.goal,
                    "executor": task.executor.value,
                    "steps": [s.model_dump(mode="json") for s in task.steps],
                },
            )

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
            loaded = await load_plan_task(db, payload.session_id, payload.task_id)
            if not loaded:
                return

            session, plan_rec, plan, task = loaded
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

            await save_plan(db, plan_rec, plan)

        await self.schedule_ready_tasks(payload.session_id, plan.id)

    async def on_step_failed(self, payload: StepCompleted) -> None:
        async with SessionLocal() as db:
            loaded = await load_plan_task(db, payload.session_id, payload.task_id)
            if not loaded:
                return

            session, plan_rec, plan, task = loaded
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
                    step.kind = StepKind.CLI_COMMAND
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
                    details={
                        "error": payload.error,
                        "hint": hint,
                        "category": category.value,
                    },
                )

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

            await save_plan(db, plan_rec, plan)

        await self.maybe_finalize_session(payload.session_id, plan.id)

    async def on_verification_completed(self, payload: VerificationCompleted) -> None:
        async with SessionLocal() as db:
            loaded = await load_plan_task(db, payload.session_id, payload.task_id)
            if not loaded:
                return

            session, plan_rec, plan, task = loaded

            if payload.passed:
                task.status = TaskStatus.VERIFIED
                task.outputs["verification"] = payload.details
            else:
                task.status = TaskStatus.FAILED
                task.error = f"Verification failed: {payload.details}"

            await save_plan(db, plan_rec, plan)

        if payload.passed:
            await self.schedule_ready_tasks(payload.session_id, payload.plan_id)

        await self.maybe_finalize_session(payload.session_id, payload.plan_id)

    async def maybe_finalize_session(self, session_id: str, plan_id: str) -> None:
        async with SessionLocal() as db:
            loaded = await load_plan(db, session_id)
            if not loaded:
                return

            session, plan_rec, plan = loaded

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

            from sqlalchemy.orm.attributes import flag_modified

            flag_modified(session, "state")
            await db.commit()

    def _merge_task_result(self, task: Subtask) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        for idx, step in enumerate(task.steps):
            merged[f"step_{idx}_{step.executor.value}"] = step.result or {}
        merged["artifacts"] = task.artifacts
        return merged
