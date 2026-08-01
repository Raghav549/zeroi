from enum import Enum

from .schemas import Subtask


class FailureCategory(str, Enum):
    EXPLORATION_FAILURE = "EXPLORATION_FAILURE"
    ACTION_LOOP = "ACTION_LOOP"
    LOST_STATE = "LOST_STATE"
    UI_MISREADING = "UI_MISREADING"
    POPUP_INTERFERENCE = "POPUP_INTERFERENCE"
    PHYSICAL_WIDGET_FAILURE = "PHYSICAL_WIDGET_FAILURE"
    CAPTCHA = "CAPTCHA"
    NETWORK = "NETWORK"
    EXPIRED_SESSION = "EXPIRED_SESSION"
    PERMISSION_DIALOG = "PERMISSION_DIALOG"
    BLANK_PAGE = "BLANK_PAGE"
    APP_CRASH = "APP_CRASH"
    UNKNOWN = "UNKNOWN"


class RecoveryStrategy(str, Enum):
    RETRY = "RETRY"
    REPLAN = "REPLAN"
    SWITCH_EXECUTOR = "SWITCH_EXECUTOR"
    REQUEST_HUMAN = "REQUEST_HUMAN"
    ABORT = "ABORT"


def classify_error(error: str, task: Subtask | None = None) -> FailureCategory:
    e = error.lower()

    if "captcha" in e:
        return FailureCategory.CAPTCHA
    if "popup" in e or "dialog" in e or "permission" in e:
        return FailureCategory.PERMISSION_DIALOG
    if "network" in e or "timeout" in e or "connection" in e:
        return FailureCategory.NETWORK
    if "session" in e and ("expired" in e or "login" in e):
        return FailureCategory.EXPIRED_SESSION
    if "blank" in e or "empty page" in e:
        return FailureCategory.BLANK_PAGE
    if "crash" in e:
        return FailureCategory.APP_CRASH
    if "not found" in e or "misread" in e or "locator" in e:
        return FailureCategory.UI_MISREADING
    if "loop" in e:
        return FailureCategory.ACTION_LOOP
    if "state" in e and "lost" in e:
        return FailureCategory.LOST_STATE

    if task and task.attempts >= 2:
        return FailureCategory.ACTION_LOOP

    return FailureCategory.UNKNOWN


class RecoveryEngine:
    def decide(self, category: FailureCategory, attempts: int) -> tuple[RecoveryStrategy, str]:
        if attempts >= 3:
            return RecoveryStrategy.REQUEST_HUMAN, "Repeated failures; requesting user assistance."

        mapping = {
            FailureCategory.NETWORK: (RecoveryStrategy.RETRY, "Retry with backoff; network issue detected."),
            FailureCategory.POPUP_INTERFERENCE: (
                RecoveryStrategy.RETRY,
                "Retry after detecting and dismissing popup/dialog.",
            ),
            FailureCategory.PERMISSION_DIALOG: (
                RecoveryStrategy.RETRY,
                "Retry with permission-dialog handling and visual grounding.",
            ),
            FailureCategory.UI_MISREADING: (
                RecoveryStrategy.RETRY,
                "Retry with zoom-in inspection, OCR, and alternate element grounding.",
            ),
            FailureCategory.BLANK_PAGE: (
                RecoveryStrategy.RETRY,
                "Reload or wait, then retry.",
            ),
            FailureCategory.ACTION_LOOP: (
                RecoveryStrategy.REPLAN,
                "Action loop detected; replan with alternate route.",
            ),
            FailureCategory.LOST_STATE: (
                RecoveryStrategy.REPLAN,
                "Execution state lost; replan from last verified checkpoint.",
            ),
            FailureCategory.CAPTCHA: (
                RecoveryStrategy.REQUEST_HUMAN,
                "CAPTCHA requires user approval or manual solve.",
            ),
            FailureCategory.EXPIRED_SESSION: (
                RecoveryStrategy.REQUEST_HUMAN,
                "Session expired; user login approval required.",
            ),
            FailureCategory.APP_CRASH: (
                RecoveryStrategy.REPLAN,
                "Application crashed; restart subtask with recovery checkpoint.",
            ),
            FailureCategory.PHYSICAL_WIDGET_FAILURE: (
                RecoveryStrategy.SWITCH_EXECUTOR,
                "Physical widget control failed; switch to CLI/API if possible.",
            ),
            FailureCategory.EXPLORATION_FAILURE: (
                RecoveryStrategy.REPLAN,
                "Exploration failed; replan with DeepSearch evidence.",
            ),
            FailureCategory.UNKNOWN: (
                RecoveryStrategy.RETRY,
                "Unknown failure; retry with additional observation.",
            ),
        }
        return mapping.get(category, (RecoveryStrategy.RETRY, "Retry."))
