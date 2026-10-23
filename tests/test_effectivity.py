from datetime import datetime as D
import json
from pathlib import Path
import pytest

from sales_dw.effectivity import insert_effective, as_of, enrich_inferred


def test_late_version_splits_intervals_against_independent_golden():
    root = Path(__file__).resolve().parents[1]
    expected = json.loads((root / "tests/fixtures/kimball/expected.json").read_text())
    rows = expected["scd2_versions"]
    key_map = {D.fromisoformat(v["valid_from"]): v["surrogate_key"] for v in rows}
    versions = []
    for index in (0, 2, 1):  # Late arrival between two already known versions.
        row = rows[index]
        versions = insert_effective(versions, D.fromisoformat(row["valid_from"]), row["category"], key_map.__getitem__)
    actual = [{"surrogate_key": v.surrogate_key, "valid_from": str(v.valid_from), "valid_to": str(v.valid_to) if v.valid_to else None,
               "category": v.category, "is_current": v.is_current} for v in versions]
    assert actual == rows
    assert [as_of(versions, D.fromisoformat(t)) for t in ("2023-12-31", "2024-01-01", "2024-01-15", "2024-02-15")] == expected["scd2_lookup_keys"]
    assert insert_effective(versions, D(2024, 1, 15), "wellness", key_map.__getitem__) == versions
    with pytest.raises(ValueError, match="Conflicting"):
        insert_effective(versions, D(2024, 1, 15), "other", key_map.__getitem__)


def test_inferred_enrichment_preserves_allocated_key():
    member = {"surrogate_key": 501, "natural_key": "synthetic:p99", "is_inferred": True}
    enriched = enrich_inferred(member, {"category": "wellness"})
    assert enriched["surrogate_key"] == 501 and not enriched["is_inferred"]
    with pytest.raises(ValueError):
        enrich_inferred(member, {"surrogate_key": 999})
