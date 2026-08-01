from fastapi import Header, HTTPException

from .config import settings
from .schemas import RiskLevel


async def require_auth(
    authorization: str | None = Header(default=None),
    x_zeroi_key: str | None = Header(default=None),
) -> None:
    if settings.auth_disabled:
        return

    if x_zeroi_key == settings.zeroi_api_key:
        return

    if authorization == f"Bearer {settings.zeroi_api_key}":
        return

    raise HTTPException(status_code=401, detail="unauthorized")


class PolicyEngine:
    IRREVERSIBLE_KEYWORDS = {
        "delete",
        "rm",
        "remove",
        "format",
        "payment",
        "pay",
        "purchase",
        "buy",
        "book",
        "send",
        "transfer",
        "publish",
        "deploy",
        "drop",
        "truncate",
    }

    HIGH_KEYWORDS = {
        "login",
        "password",
        "install",
        "sudo",
        "ssh",
        "email",
        "message",
        "submit",
        "upload",
    }

    def classify(self, payload: dict | str) -> RiskLevel:
        text = str(payload).lower()

        if any(k in text for k in self.IRREVERSIBLE_KEYWORDS):
            return RiskLevel.IRREVERSIBLE

        if any(k in text for k in self.HIGH_KEYWORDS):
            return RiskLevel.HIGH

        return RiskLevel.LOW

    def requires_approval(self, risk: RiskLevel) -> bool:
        return risk in {RiskLevel.HIGH, RiskLevel.IRREVERSIBLE}
