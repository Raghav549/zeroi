import logging
from typing import Any

from ..ids import new_id
from ..llm import LLMClient
from ..schemas import (
    ExecutorType,
    Plan,
    RiskLevel,
    Step,
    StepKind,
    Subtask,
    TaskStatus,
)

log = logging.getLogger(__name__)

PLANNER_SYSTEM_PROMPT = """
You are the planner for zeroi, an autonomous AI operating system.
Decompose the user goal into dependency-aware subtasks.

Available executors:
- DEEPSEARCH for research, evidence, comparison, verification
- CLI for file operations, compression, conversion, scripting, batch processing
- BROWSER for websites, forms, login flows, structured extraction
- API when an official API exists
- GUI for visually grounded application interaction using Qwen-UI-Agent
- HYBRID only if a task requires multiple executors in a pipeline

Rules:
- Prefer DeepSearch before GUI when target is unknown.
- Prefer CLI for file/system structured operations.
- Prefer API when official service exists.
- Use GUI only for visually grounded apps.
- Use batchable GUI actions where possible.
- Output strict JSON.
"""

PLANNER_OUTPUT_SCHEMA = """
Return JSON:
{
  "tasks": [
    {
      "id": "task_1",
      "title": "...",
      "goal": "...",
      "executor": "DEEPSEARCH|CLI|BROWSER|API|GUI|HYBRID",
      "dependencies": [],
      "risk": "LOW|MEDIUM|HIGH|IRREVERSIBLE",
      "steps": [
        {
          "executor": "DEEPSEARCH|CLI|BROWSER|API|GUI",
          "kind": "SEARCH|CLI_COMMAND|BROWSER_FLOW|API_CALL|GUI_OBJECTIVE|GUI_BATCH",
          "payload": {}
        }
      ]
    }
  ]
}
"""


class PlannerEngine:
    def __init__(self) -> None:
        self.llm = LLMClient()

    async def create_plan(self, session_id: str, goal: str, context: dict[str, Any]) -> Plan:
        heuristic = self._heuristic_tasks(goal, context)
        llm_plan = await self._llm_plan(goal, context)

        tasks = self._normalize_tasks(llm_plan.get("tasks") or heuristic, goal)
        plan = Plan(session_id=session_id, goal=goal, tasks=tasks, context=context)
        self._validate_plan(plan)
        return plan

    async def replan(
        self,
        session_id: str,
        goal: str,
        context: dict[str, Any],
        current_plan: dict[str, Any] | None,
        failed_task: dict[str, Any] | None,
        error: str | None,
    ) -> Plan:
        base = Plan.model_validate(current_plan) if current_plan else None

        if base:
            preserved = [t for t in base.tasks if t.status in {TaskStatus.COMPLETED, TaskStatus.VERIFIED}]
            failed = [t for t in base.tasks if failed_task and t.id == failed_task.get("id")]
            pending = [
                t
                for t in base.tasks
                if t.status not in {TaskStatus.COMPLETED, TaskStatus.VERIFIED}
                and not (failed_task and t.id == failed_task.get("id"))
            ]

            corrective = Subtask(
                id=new_id("task"),
                title="Recovery and replan",
                goal=f"Recover from failure: {error or 'unknown'} and continue original objective",
                executor=ExecutorType.DEEPSEARCH,
                dependencies=[t.id for t in preserved],
                risk=RiskLevel.LOW,
                steps=[
                    Step(
                        executor=ExecutorType.DEEPSEARCH,
                        kind=StepKind.SEARCH,
                        payload={
                            "objective": f"Diagnose failure and identify correct target or alternate method. Error: {error}",
                            "max_rounds": 2,
                        },
                    )
                ],
            )

            tasks = preserved + [corrective] + pending
            if failed:
                for t in failed:
                    t.status = TaskStatus.PENDING
                    t.current_step = 0
                    t.attempts += 1
                    if t.steps:
                        t.steps[t.current_step].payload["recovery_hint"] = error
                tasks += failed

            plan = Plan(
                id=base.id,
                session_id=session_id,
                goal=goal,
                version=base.version + 1,
                tasks=tasks,
                context=context,
            )
        else:
            plan = await self.create_plan(session_id, goal, context)

        self._validate_plan(plan)
        return plan

    async def _llm_plan(self, goal: str, context: dict[str, Any]) -> dict[str, Any]:
        messages = [
            {"role": "system", "content": PLANNER_SYSTEM_PROMPT + PLANNER_OUTPUT_SCHEMA},
            {
                "role": "user",
                "content": f"Goal: {goal}\nContext: {context}\n\nReturn only JSON.",
            },
        ]
        return await self.llm.chat_json(messages)

    def _heuristic_tasks(self, goal: str, context: dict[str, Any]) -> list[dict[str, Any]]:
        g = goal.lower()
        tasks: list[dict[str, Any]] = []
        deps: list[str] = []

        if any(k in g for k in ["research", "find", "compare", "verify", "evidence", "paper", "docs"]):
            tid = "task_search"
            tasks.append(
                {
                    "id": tid,
                    "title": "DeepSearch evidence",
                    "goal": "Gather evidence and identify correct target",
                    "executor": "DEEPSEARCH",
                    "dependencies": [],
                    "risk": "LOW",
                    "steps": [
                        {
                            "executor": "DEEPSEARCH",
                            "kind": "SEARCH",
                            "payload": {"objective": goal, "max_rounds": 3},
                        }
                    ],
                }
            )
            deps.append(tid)

        if any(k in g for k in ["file", "zip", "convert", "compress", "image", "ffmpeg", "pandoc", "script"]):
            tid = "task_cli"
            tasks.append(
                {
                    "id": tid,
                    "title": "CLI structured operation",
                    "goal": "Perform structured file/system operation",
                    "executor": "CLI",
                    "dependencies": deps.copy(),
                    "risk": "MEDIUM",
                    "steps": [
                        {
                            "executor": "CLI",
                            "kind": "CLI_COMMAND",
                            "payload": {"command": ["echo", goal], "timeout": 60},
                        }
                    ],
                }
            )
            deps.append(tid)

        if any(k in g for k in ["website", "web", "login", "form", "download", "url", "http"]):
            tid = "task_browser"
            tasks.append(
                {
                    "id": tid,
                    "title": "Browser automation",
                    "goal": "Interact with website and extract structured result",
                    "executor": "BROWSER",
                    "dependencies": deps.copy(),
                    "risk": "MEDIUM",
                    "steps": [
                        {
                            "executor": "BROWSER",
                            "kind": "BROWSER_FLOW",
                            "payload": {
                                "actions": [
                                    {"type": "goto", "url": context.get("url", "about:blank")},
                                    {"type": "extract", "selector": "body", "as": "text"},
                                ]
                            },
                        }
                    ],
                }
            )
            deps.append(tid)

        if any(k in g for k in ["app", "desktop", "android", "gui", "click", "window", "ui"]):
            tid = "task_gui"
            tasks.append(
                {
                    "id": tid,
                    "title": "GUI execution with Qwen-UI-Agent",
                    "goal": "Execute visually grounded GUI operation",
                    "executor": "GUI",
                    "dependencies": deps.copy(),
                    "risk": "MEDIUM",
                    "steps": [
                        {
                            "executor": "GUI",
                            "kind": "GUI_OBJECTIVE",
                            "payload": {"objective": goal, "device": context.get("device")},
                        }
                    ],
                }
            )
            deps.append(tid)

        if not tasks:
            tasks.append(
                {
                    "id": "task_default_search",
                    "title": "Understand objective",
                    "goal": "Use DeepSearch to clarify objective",
                    "executor": "DEEPSEARCH",
                    "dependencies": [],
                    "risk": "LOW",
                    "steps": [
                        {
                            "executor": "DEEPSEARCH",
                            "kind": "SEARCH",
                            "payload": {"objective": goal, "max_rounds": 1},
                        }
                    ],
                }
            )

        return tasks

    def _normalize_tasks(self, raw_tasks: list[dict[str, Any]], goal: str) -> list[Subtask]:
        tasks: list[Subtask] = []

        for idx, raw in enumerate(raw_tasks):
            try:
                executor = ExecutorType(raw.get("executor", "DEEPSEARCH"))
            except ValueError:
                executor = ExecutorType.DEEPSEARCH

            steps_raw = raw.get("steps") or []
            steps: list[Step] = []

            for s in steps_raw:
                try:
                    sexec = ExecutorType(s.get("executor", executor.value))
                    skind = StepKind(s.get("kind", self._default_kind(sexec)))
                except ValueError:
                    sexec = executor
                    skind = self._default_kind(executor)

                steps.append(
                    Step(
                        executor=sexec,
                        kind=skind,
                        payload=s.get("payload", {}),
                    )
                )

            if not steps:
                steps.append(
                    Step(
                        executor=executor if executor != ExecutorType.HYBRID else ExecutorType.DEEPSEARCH,
                        kind=self._default_kind(executor),
                        payload={"objective": raw.get("goal", goal)},
                    )
                )

            try:
                risk = RiskLevel(raw.get("risk", "LOW"))
            except ValueError:
                risk = RiskLevel.LOW

            tasks.append(
                Subtask(
                    id=raw.get("id") or f"task_{idx + 1}",
                    title=raw.get("title", f"Task {idx + 1}"),
                    goal=raw.get("goal", goal),
                    executor=executor,
                    dependencies=raw.get("dependencies", []),
                    steps=steps,
                    risk=risk,
                    inputs=raw.get("inputs", {}),
                    outputs=raw.get("outputs", {}),
                )
            )

        return tasks

    def _default_kind(self, executor: ExecutorType) -> StepKind:
        return {
            ExecutorType.GUI: StepKind.GUI_OBJECTIVE,
            ExecutorType.CLI: StepKind.CLI_COMMAND,
            ExecutorType.BROWSER: StepKind.BROWSER_FLOW,
            ExecutorType.API: StepKind.API_CALL,
            ExecutorType.DEEPSEARCH: StepKind.SEARCH,
            ExecutorType.HUMAN: StepKind.HUMAN,
            ExecutorType.HYBRID: StepKind.GUI_OBJECTIVE,
        }.get(executor, StepKind.SEARCH)

    def _validate_plan(self, plan: Plan) -> None:
        ids = {t.id for t in plan.tasks}

        for task in plan.tasks:
            task.dependencies = [d for d in task.dependencies if d in ids and d != task.id]

        # Very simple cycle breaker: remove dependencies that point forward in a topological attempt.
        seen = set()
        ordered: list[Subtask] = []
        remaining = list(plan.tasks)

        for _ in range(len(remaining) + 1):
            progressed = False
            for task in list(remaining):
                if all(dep in seen for dep in task.dependencies):
                    ordered.append(task)
                    seen.add(task.id)
                    remaining.remove(task)
                    progressed = True
            if not remaining:
                break
            if not progressed:
                # Break cycles by clearing dependencies of first remaining task.
                remaining[0].dependencies = []

        plan.tasks = ordered
