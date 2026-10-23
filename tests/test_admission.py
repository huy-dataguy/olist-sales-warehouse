from sales_dw.admission import batch_identity, source_timestamp
import pytest


def test_optional_airflow_month_has_same_identity_as_cli():
    base = {"artifact_sha256": "a"*64, "plan_id": "full-v2"}
    assert batch_identity(base) == batch_identity({**base, "month": None}) == batch_identity({**base, "month": ""})
    assert batch_identity(base) != batch_identity({**base, "month": "2018-08"})


def test_source_timestamp_checks_calendar_not_just_format():
    assert source_timestamp("2018-08-31 23:59:59")
    with pytest.raises(ValueError):
        source_timestamp("2018-02-30 00:00:00")
