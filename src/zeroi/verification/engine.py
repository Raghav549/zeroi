from typing import Any

from ..schemas import VerificationCompleted, VerificationRequest


class VerificationEngine:
    async def verify(self, request: VerificationRequest) -> VerificationCompleted:
        checks: dict[str, Any] = {}
        passed = True
        score = 1.0

        outputs = request.outputs or {}

        if "returncode" in outputs:
            ok = outputs.get("returncode") == 0
            checks["cli_returncode"] = ok
            passed = passed and ok

        if "extracted" in outputs:
            ok = bool(outputs.get("extracted"))
            checks["browser_extracted"] = ok
            passed = passed and ok

        if "answer" in outputs:
            ok = bool(outputs.get("answer"))
            checks["deepsearch_answer"] = ok
            passed = passed and ok

        if "error" in outputs and outputs["error"]:
            passed = False
            checks["error"] = False

        return VerificationCompleted(
            session_id=request.session_id,
            plan_id=request.plan_id,
            task_id=request.task_id,
            passed=passed,
            score=score if passed else 0.0,
            details=checks,
            evidence=[],
        )
