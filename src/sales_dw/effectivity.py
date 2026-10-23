"""Explicit business-effective history. Used only for declared synthetic fixtures.

The Olist snapshot does NOT provide effective changes and does not call this path.
Key allocation is injected; a warehouse registry supplies stable integer keys.
"""
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Callable


@dataclass(frozen=True)
class Version:
    surrogate_key: int
    valid_from: datetime
    valid_to: datetime | None
    category: str

    @property
    def is_current(self):
        return self.valid_to is None


def insert_effective(versions: list[Version], effective_at: datetime, category: str,
                     allocate: Callable[[datetime], int]) -> list[Version]:
    """Recompute half-open intervals, preserving all existing version identities."""
    for old in versions:
        if old.valid_from == effective_at:
            if old.category != category:
                raise ValueError("Conflicting payload at the same effective revision")
            return list(versions)
    ordered = sorted([*versions, Version(allocate(effective_at), effective_at, None, category)], key=lambda v: v.valid_from)
    return [replace(v, valid_to=ordered[i+1].valid_from if i+1 < len(ordered) else None) for i, v in enumerate(ordered)]


def as_of(versions, timestamp):
    matches = [v.surrogate_key for v in versions if v.valid_from <= timestamp and (v.valid_to is None or timestamp < v.valid_to)]
    if len(matches) > 1:
        raise ValueError("Overlapping effectivity intervals")
    return matches[0] if matches else 0


def enrich_inferred(member, attributes):
    if not member["is_inferred"]:
        raise ValueError("Only an inferred member can use enrichment")
    if {"surrogate_key", "natural_key", "is_inferred"} & attributes.keys():
        raise ValueError("Enrichment must preserve identity")
    return {**member, **attributes, "is_inferred": False}
