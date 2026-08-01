from zeroi.actions import group_gui_actions
from zeroi.schemas import ActionStep, RiskLevel


def test_group_gui_actions_batches_low_risk():
    actions = [ActionStep(type="click", target=f"button-{i}") for i in range(10)]
    batches = group_gui_actions(actions, max_batch=4)

    assert len(batches) == 3
    assert len(batches[0].actions) == 4
    assert len(batches[1].actions) == 4
    assert len(batches[2].actions) == 2


def test_confirmation_action_is_isolated():
    actions = [
        ActionStep(type="click", target="ok"),
        ActionStep(type="click", target="pay", require_confirmation=True, risk=RiskLevel.IRREVERSIBLE),
        ActionStep(type="click", target="next"),
    ]
    batches = group_gui_actions(actions, max_batch=8)

    assert len(batches) == 3
    assert batches[1].actions[0].target == "pay"
