"""The converted sites must parse exactly what they parsed before.

`int(callback.data.split(":")[N])` and `parse_callback_int(callback.data, prefix)` have to
agree on every payload the bot actually emits. This checks that equivalence directly for
each converted handler's real prefix, so an index mistranslation shows up here instead of
as a broken button in production.
"""
from __future__ import annotations

import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from src.core.callbacks import parse_callback_int  # noqa: E402

# (prefix, id) for every callback the converted handlers answer.
CASES = [
    ("ticket_reply:", "42"),
    ("canned:", "3"),
    ("ticket_close:", "7"),
    ("ticket_close_yes:", "7"),
    ("ticket_take:", "12"),
    ("ticket_skip:", "12"),
]


def test_equivalent_on_real_payloads():
    for prefix, value in CASES:
        payload = f"{prefix}{value}"
        old = int(payload.split(":")[prefix.count(":")])
        assert parse_callback_int(payload, prefix) == old, payload


def test_equivalent_on_hostile_payloads():
    """Where they must differ: malformed data. Old raised or mis-parsed."""
    for prefix, _ in CASES:
        # missing segment
        assert parse_callback_int(prefix.rstrip(":"), prefix) is None
        # non-numeric
        assert parse_callback_int(f"{prefix}abc", prefix) is None
        # extra segment - old would have silently taken the first
        assert parse_callback_int(f"{prefix}5:9", prefix) is None


def test_handlers_guarded():
    src_dir = pathlib.Path(__file__).resolve().parents[1] / "src"
    sites = []
    for p in src_dir.rglob("*.py"):
        if p.name == "callbacks.py":
            continue
        lines = p.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if re.match(r"^\s*(from|import)\s", line):
                continue
            if "= parse_callback_int(" in line:
                window = "\n".join(lines[i + 1 : i + 4])
                if "is None" not in window:
                    sites.append(f"{p.name}:{i + 1}")
    assert not sites, f"unguarded parse sites: {sites}"
