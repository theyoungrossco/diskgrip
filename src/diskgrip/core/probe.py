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

# -b gives raw byte counts for size/fsavail/fssize/fsused; -O asks for every
# column lsblk knows (missing columns are absent from JSON, not errors).
PROBE_COMMAND = ["lsblk", "-b", "-J", "-O"]

# GPT partition type GUIDs → flag names (lower-cased for matching).
_PARTTYPE_GUID_FLAGS: dict[str, list[str]] = {
    "c12a7328-f81f-11d2-ba4b-00a0c93ec93b": ["boot", "esp"],
    "21686148-6449-6e6f-744e-656564454649": ["bios_grub"],
    "e6d6d379-f507-44c2-a23c-238f2a3df928": ["lvm"],
    "a19d880f-05fc-4d3b-a006-743f0f84911e": ["raid"],
    "0657fd6d-a4ab-43c4-84e5-0933c84b4f4f": ["swap"],
}

# Human parttypename substrings → flag names.
_PARTTYPE_NAME_FLAGS: dict[str, list[str]] = {
    "EFI System": ["boot", "esp"],
    "BIOS boot": ["bios_grub"],
    "Linux LVM": ["lvm"],
    "Linux RAID": ["raid"],
    "Linux swap": ["swap"],
}


def _fmt_bytes(n: int | None) -> str:
    """Format a raw byte count as a compact human-readable string."""
    if n is None:
        return ""
    for factor, suffix in [(1 << 40, "T"), (1 << 30, "G"), (1 << 20, "M"), (1 << 10, "K")]:
        if n >= factor:
            val = n / factor
            return f"{val:.1f}{suffix}" if val < 100 else f"{round(val)}{suffix}"
    return f"{n}B"


def _parse_partflags(node: dict) -> list[str]:
    """Extract flag names from parttypename, parttype GUID, and partflags."""
    flags: set[str] = set()
    guid = (node.get("parttype") or "").lower()
    flags.update(_PARTTYPE_GUID_FLAGS.get(guid, []))
    partname = node.get("parttypename") or ""
    for key, flist in _PARTTYPE_NAME_FLAGS.items():
        if key.lower() in partname.lower():
            flags.update(flist)
    raw = node.get("partflags")
    if raw and isinstance(raw, str):
        for f in raw.split(","):
            f = f.strip().lower()
            if f:
                flags.add(f)
    return sorted(flags)


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
    raw_size = node.get("size")
    if isinstance(raw_size, int):
        size_bytes: int | None = raw_size
        size: str = _fmt_bytes(raw_size)
    else:
        size_bytes = None
        size = raw_size or ""

    raw_start = node.get("start")
    start: int | None = int(raw_start) if isinstance(raw_start, (int, float)) else None

    raw_fsavail = node.get("fsavail")
    fsavail: str | None = _fmt_bytes(raw_fsavail) if isinstance(raw_fsavail, int) else raw_fsavail

    return BlockDevice(
        name=node.get("name", ""),
        kind=node.get("type", ""),
        size=size,
        size_bytes=size_bytes,
        start=start,
        fstype=node.get("fstype"),
        fsver=node.get("fsver"),
        label=node.get("label"),
        uuid=node.get("uuid"),
        fsavail=fsavail,
        fsuse=node.get("fsuse%"),
        mountpoints=_clean_mountpoints(node),
        model=(node.get("model") or None),
        serial=node.get("serial"),
        rotational=_as_bool(node.get("rota")),
        transport=node.get("tran"),
        parttype=node.get("parttypename"),
        removable=bool(_as_bool(node.get("rm"))),
        readonly=bool(_as_bool(node.get("ro"))),
        partflags=_parse_partflags(node),
        pttype=node.get("pttype"),
        ptuuid=node.get("ptuuid"),
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
