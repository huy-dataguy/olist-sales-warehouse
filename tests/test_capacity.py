import pytest
from sales_dw.capacity import enforce


def test_backfill_stops_before_hard_budget_and_preserves_recovery_space():
    assert not enforce(30_000_000_000, 20_000_000_000)["warning"]
    assert enforce(57_000_000_000, 20_000_000_000)["warning"]
    with pytest.raises(RuntimeError, match="90%"):
        enforce(62_000_000_000, 20_000_000_000)
    with pytest.raises(RuntimeError, match="5 GB"):
        enforce(30_000_000_000, 4_999_999_999)
