"""Read block-storage state from a host via ``lsblk``'s JSON output.

Mirrors netgrip's ``core/probe.py``: one read command, parsed into the
:mod:`diskgrip.core.model` dataclasses, defensively (``.get`` everywhere) so a
column missing on an older util-linux just leaves a field ``None`` instead of
failing the whole read.
"""

from __future__ import annotations

import json

from diskgrip.core.model import BlockDevice
from diskgrip.core.runner import Runner

# ``-O`` asks lsblk for every column it knows; we then pick the ones we model.
# Using ``-O`` (rather than a fixed ``-o`` list) means lsblk never errors on a
# column name an older build doesn't recognise — the key is simply absent and
# the corresponding field stays None. ``-b`` is intentionally *not* used: we
# keep lsblk's human sizes verbatim for display.
PROBE_COMMAND = ["lsblk", "-J", "-O"]


def _clean_mountpoints(node: dict) -> list[str]:
    """Mountpoints as a clean list of strings.

    Modern lsblk reports ``mountpoints`` (a list that contains ``null`` for an
    unmounted device); older builds report a single ``mountpoint`` string. Both
    are normalised to a list with the empty/None entries dropped.
    """
    points = node.get("mountpoints")
    if isinstance(points, list):
        return [p for p in points if p]
    single = node.get("mountpoint")
    return [single] if single else []


def _as_bool(value) -> bool | None:
    """lsblk JSON booleans are real bools, but tolerate "0"/"1"/"true" too."""
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return None
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes")
    return bool(value)


def parse_device(node: dict) -> BlockDevice:
    """Build a :class:`BlockDevice` (and its children) from one lsblk node."""
    return BlockDevice(
        name=node.get("name", ""),
        kind=node.get("type", ""),
        size=node.get("size") or "",
        fstype=node.get("fstype"),
        fsver=node.get("fsver"),
        label=node.get("label"),
        uuid=node.get("uuid"),
        fsavail=node.get("fsavail"),
        fsuse=node.get("fsuse%"),
        mountpoints=_clean_mountpoints(node),
        model=(node.get("model") or None),
        serial=node.get("serial"),
        rotational=_as_bool(node.get("rota")),
        transport=node.get("tran"),
        parttype=node.get("parttypename"),
        removable=bool(_as_bool(node.get("rm"))),
        readonly=bool(_as_bool(node.get("ro"))),
        children=[parse_device(child) for child in node.get("children", [])],
    )


def parse_lsblk_json(out: str) -> list[BlockDevice]:
    """Parse ``lsblk -J`` stdout into the top-level block devices."""
    try:
        payload = json.loads(out)
    except json.JSONDecodeError as exc:
        raise ValueError(f"lsblk did not return valid JSON: {exc}") from exc
    return [parse_device(node) for node in payload.get("blockdevices", [])]


def probe(runner: Runner) -> list[BlockDevice]:
    """Read the host's block devices through ``runner`` (read-only)."""
    return parse_lsblk_json(runner.run(PROBE_COMMAND))
