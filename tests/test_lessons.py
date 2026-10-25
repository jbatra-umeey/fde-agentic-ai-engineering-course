import pytest
from jev_cli.lessons import run_lesson


@pytest.mark.parametrize("number", range(1, 11))
async def test_agent_engineering_lesson(number):
    result = await run_lesson(number)
    assert result
    if number == 5:
        assert result["after_opt_in"] and not result["after_forget"]
    if number == 6:
        assert (
            result["router_then_parallel_specialists"]["recommendation"]
            == "PROCEED_TO_HUMAN_REVIEW"
        )
    if number == 8:
        assert result["gate"]
    if number == 9:
        assert result["final"]["status"] == "succeeded"
    if number == 10:
        assert any(s["name"] == "tool.execute" for s in result["spans"])
