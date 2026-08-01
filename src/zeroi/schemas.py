from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from .ids import new_id


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class ZeroiModel(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class ExecutorType(str, Enum):
    GUI = "GUI"
    CLI = "CLI"
    BROWSER = "BROWSER"
    API = "API"
    DEEPSEARCH = "DEEPSEARCH"
    HUMAN = "HUMAN"
    HYBRID = "HYBRID"


class StepKind(str, Enum):
    GUI_OBJECTIVE = "GUI_OBJECTIVE"
    GUI_BATCH = "GUI_BATCH"
    CLI_COMMAND = "CLI_COMMAND"
    BROWSER_FLOW = "BROWSER_FLOW"
    API_CALL = "API_CALL"
    SEARCH = "SEARCH"
    VERIFY = "VERIFY"
    HUMAN = "HUMAN"


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    COMPLETED = "COMPLETED"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REPLANNING = "REPLANNING"


class StepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    IRREVERSIBLE = "IRREVERSIBLE"


class MemoryKind(str, Enum):
    PROFILE = "PROFILE"
    PREFERENCE = "PREFERENCE"
    FEEDBACK = "FEEDBACK"
    EPISODIC = "EPISODIC"
    SEMANTIC = "SEMANTIC"
    RELATIONSHIP = "RELATIONSHIP"
    TASK = "TASK"
    CONTEXT = "CONTEXT"


class DeviceRef(ZeroiModel):
    device_id: str
    display_id: Optional[str] = None
    app_id: Optional[str] = None
    os: Optional[str] = None


class Observation(ZeroiModel):
    id: str = Field(default_factory=lambda: new_id("obs"))
    ts: str = Field(default_factory=utcnow)
    device: Optional[DeviceRef] = None
    screenshot_uri: Optional[str] = None
    ui_tree: Optional[dict[str, Any]] = None
    ocr: Optional[list[dict[str, Any]]] = None
    focused_app: Optional[str] = None


class ActionStep(ZeroiModel):
    id: str = Field(default_factory=lambda: new_id("act"))
    type: str
    target: Optional[str] = None
    coordinates: Optional[list[int]] = None
    text: Optional[str] = None
    keys: Optional[list[str]] = None
    selector: Optional[str] = None
    expected_state: Optional[dict[str, Any]] = None
    risk: RiskLevel = RiskLevel.LOW
    require_confirmation: bool = False


class GUIBatch(ZeroiModel):
    id: str = Field(default_factory=lambda: new_id("guibatch"))
    device: Optional[DeviceRef] = None
    preconditions: list[dict[str, Any]] = Field(default_factory=list)
    actions: list[ActionStep] = Field(default_factory=list)
    postconditions: list[dict[str, Any]] = Field(default_factory=list)
    stop_on_failure: bool = True
    max_duration_seconds: int = 120


class Step(ZeroiModel):
    id: str = Field(default_factory=lambda: new_id("step"))
    executor: ExecutorType
    kind: StepKind
    payload: dict[str, Any] = Field(default_factory=dict)
    status: StepStatus = StepStatus.PENDING
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None


class Subtask(ZeroiModel):
    id: str = Field(default_factory=lambda: new_id("task"))
    title: str
    goal: str
    executor: ExecutorType
    status: TaskStatus = TaskStatus.PENDING
    dependencies: list[str] = Field(default_factory=list)
    steps: list[Step] = Field(default_factory=list)
    current_step: int = 0
    attempts: int = 0
    max_attempts: int = 3
    timeout_seconds: int = 600
    risk: RiskLevel = RiskLevel.LOW
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    artifacts: list[str] = Field(default_factory=list)
    observations: list[Observation] = Field(default_factory=list)


class Plan(ZeroiModel):
    id: str = Field(default_factory=lambda: new_id("plan"))
    session_id: str
    goal: str
    version: int = 1
    tasks: list[Subtask] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utcnow)


class SessionStatus(str, Enum):
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    RUNNING = "RUNNING"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class SessionState(ZeroiModel):
    id: str
    user_id: Optional[str] = None
    goal: str
    status: SessionStatus = SessionStatus.CREATED
    plan_id: Optional[str] = None
    shared_memory: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[str] = Field(default_factory=list)
    final_response: Optional[dict[str, Any]] = None
    created_at: str = Field(default_factory=utcnow)
    updated_at: str = Field(default_factory=utcnow)


class RequestCreated(ZeroiModel):
    request_id: str = Field(default_factory=lambda: new_id("req"))
    session_id: str
    user_id: Optional[str] = None
    goal: str
    context: dict[str, Any] = Field(default_factory=dict)


class PlanRequest(ZeroiModel):
    session_id: str
    goal: str
    context: dict[str, Any] = Field(default_factory=dict)
    current_plan: Optional[dict[str, Any]] = None
    failed_task: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    replan: bool = False


class PlanCompleted(ZeroiModel):
    plan: Plan
    replan: bool = False


class StepExecutionRequest(ZeroiModel):
    session_id: str
    task_id: str
    step_id: str
    executor: ExecutorType
    kind: StepKind
    payload: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)


class StepCompleted(ZeroiModel):
    session_id: str
    task_id: str
    step_id: str
    status: StepStatus
    result: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[str] = Field(default_factory=list)
    observations: list[Observation] = Field(default_factory=list)
    error: Optional[str] = None


class VerificationRequest(ZeroiModel):
    session_id: str
    plan_id: str
    task_id: str
    outputs: dict[str, Any] = Field(default_factory=dict)


class VerificationCompleted(ZeroiModel):
    session_id: str
    plan_id: str
    task_id: str
    passed: bool
    score: float = 1.0
    details: dict[str, Any] = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list)


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ApprovalRequestModel(ZeroiModel):
    id: str = Field(default_factory=lambda: new_id("approval"))
    session_id: str
    task_id: Optional[str] = None
    step_id: Optional[str] = None
    risk: RiskLevel = RiskLevel.HIGH
    title: str
    details: dict[str, Any] = Field(default_factory=dict)
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: str = Field(default_factory=utcnow)


class ApprovalDecided(ZeroiModel):
    id: str
    approved: bool
    reason: Optional[str] = None


class MemoryWrite(ZeroiModel):
    user_id: Optional[str] = None
    kind: MemoryKind
    content: str
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryQuery(ZeroiModel):
    user_id: Optional[str] = None
    kind: Optional[MemoryKind] = None
    query: str
    limit: int = 10


class MemoryRecordModel(ZeroiModel):
    id: str = Field(default_factory=lambda: new_id("mem"))
    user_id: Optional[str] = None
    kind: MemoryKind
    content: str
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    score: float = 0.0
    created_at: str = Field(default_factory=utcnow)


class EventUrgency(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class EventModel(ZeroiModel):
    id: str = Field(default_factory=lambda: new_id("event"))
    source: str
    kind: str
    title: str
    body: Optional[str] = None
    entities: dict[str, Any] = Field(default_factory=dict)
    urgency: EventUrgency = EventUrgency.NORMAL
    actions: list[dict[str, Any]] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)
    ts: str = Field(default_factory=utcnow)


class Affair(ZeroiModel):
    id: str = Field(default_factory=lambda: new_id("affair"))
    kind: str
    title: str
    state: dict[str, Any] = Field(default_factory=dict)
    entities: dict[str, Any] = Field(default_factory=dict)
    deadlines: list[str] = Field(default_factory=list)
    related_sessions: list[str] = Field(default_factory=list)
    updated_at: str = Field(default_factory=utcnow)


class Telemetry(ZeroiModel):
    service: str
    level: str = "INFO"
    message: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    ts: str = Field(default_factory=utcnow)
