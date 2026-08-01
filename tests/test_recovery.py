from zeroi.recovery import FailureCategory, RecoveryEngine, RecoveryStrategy, classify_error
from zeroi.schemas import Subtask, ExecutorType


def test_classify_captcha():
    task = Subtask(title="t", goal="g", executor=ExecutorType.GUI)
    assert classify_error("CAPTCHA detected", task) == FailureCategory.CAPTCHA


def test_recovery_loop_replans():
    engine = RecoveryEngine()
    strategy, _ = engine.decide(FailureCategory.ACTION_LOOP, attempts=1)
    assert strategy == RecoveryStrategy.REPLAN


def test_recovery_too_many_attempts_requests_human():
    engine = RecoveryEngine()
    strategy, _ = engine.decide(FailureCategory.UNKNOWN, attempts=5)
    assert strategy == RecoveryStrategy.REQUEST_HUMAN
