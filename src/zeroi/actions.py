import hashlib
import json
from typing import Any

from .schemas import ActionStep, GUIBatch


def stable_hash(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def action_hash(action: ActionStep) -> str:
    return stable_hash(action.model_dump(exclude={"id"}))


def batch_hash(batch: GUIBatch) -> str:
    return stable_hash([action_hash(a) for a in batch.actions])


def group_gui_actions(actions: list[ActionStep], max_batch: int = 8) -> list[GUIBatch]:
    """
    Group compatible low-risk actions into batches.
    High-risk or confirmation-required actions are isolated.
    """
    batches: list[GUIBatch] = []
    current: list[ActionStep] = []

    for action in actions:
        if action.require_confirmation:
            if current:
                batches.append(GUIBatch(actions=current))
                current = []
            batches.append(GUIBatch(actions=[action]))
            continue

        current.append(action)
        if len(current) >= max_batch:
            batches.append(GUIBatch(actions=current))
            current = []

    if current:
        batches.append(GUIBatch(actions=current))

    return batches
