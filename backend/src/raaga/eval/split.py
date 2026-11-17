"""Deterministic train/val/test assignment by recording group (never by clip)."""
from __future__ import annotations

import hashlib
from typing import Literal

Split = Literal["train", "val", "test"]


def group_split(group_id: str) -> Split:
    b = hashlib.sha1(group_id.encode("utf-8")).digest()[0] % 10
    if b in (0, 1):
        return "test"
    if b == 2:
        return "val"
    return "train"
