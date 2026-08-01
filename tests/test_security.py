from zeroi.schemas import RiskLevel
from zeroi.security import PolicyEngine


def test_policy_irreversible():
    policy = PolicyEngine()
    assert policy.classify({"command": "rm -rf /tmp/x"}) == RiskLevel.IRREVERSIBLE


def test_policy_requires_approval():
    policy = PolicyEngine()
    assert policy.requires_approval(RiskLevel.IRREVERSIBLE)
    assert not policy.requires_approval(RiskLevel.LOW)
