from decimal import Decimal
import pytest
from sales_dw.export_metrics import assert_parity, assert_forbidden_dimension
from subprocess import CompletedProcess


def test_money_is_exact_and_ratio_tolerance_is_bounded():
    expected = [{"month": "2024-01-01", "delivered_merchandise_value": Decimal("280.00"), "delivered_aov": Decimal("93.333333333333")}]
    assert_parity(expected, expected, ["month"], ["delivered_merchandise_value", "delivered_aov"])
    bad = [{**expected[0], "delivered_merchandise_value": Decimal("280.01")}]
    with pytest.raises(AssertionError):
        assert_parity(bad, expected, ["month"], ["delivered_merchandise_value"])


def test_missing_group_and_duplicate_group_are_not_silently_accepted():
    expected = [{"month": "2024-01-01", "total_orders": 4}]
    with pytest.raises(AssertionError):
        assert_parity([], expected, ["month"], ["total_orders"])
    with pytest.raises(AssertionError):
        assert_parity(expected * 2, expected, ["month"], ["total_orders"])


def test_negative_semantic_check_cannot_pass_on_unrelated_connection_error():
    assert_forbidden_dimension(CompletedProcess([], 1, "ERROR: Got error(s) during query resolution. product__category", ""))
    with pytest.raises(AssertionError):
        assert_forbidden_dimension(CompletedProcess([], 1, "", "Connection refused"))
    with pytest.raises(AssertionError):
        assert_forbidden_dimension(CompletedProcess([], 0, "", ""))
