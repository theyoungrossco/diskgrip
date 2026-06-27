"""Build command plans for block-device mutations.

Every function returns a list of argv lists ("a plan") without executing
anything. The caller shows the plan to the user for confirmation, then hands it
to :meth:`Runner.run_privileged`, which executes it as one batch.

Mirrors netgrip's ``core/actions.py``: pure Python, no Qt, each function
testable in isolation. The dangerous operations here (format, unmount) are
never auto-executed — the caller must always confirm first.
"""

from __future__ import annotations

import re

from diskgrip.core.model import BlockDevice

# Filesystem types diskgrip knows how to create. The value is the mkfs binary
# name; vfat and fat32 both map to mkfs.vfat.
_MKFS = {
    "ext4": "mkfs.ext4",
    "xfs": "mkfs.xfs",
    "btrfs": "mkfs.btrfs",
    "vfat": "mkfs.vfat",
    "fat32": "mkfs.vfat",
    "ntfs": "mkfs.ntfs",
    "exfat": "mkfs.exfat",
}

SUPPORTED_FSTYPES = sorted(_MKFS)

# A mountpoint must be an absolute path.
_MOUNTPOINT_RE = re.compile(r"^/[^\x00]*$")


def valid_mountpoint(path: str) -> bool:
    """True for a plausible absolute mountpoint path."""
    return bool(_MOUNTPOINT_RE.match(path)) and path != "/"


def valid_fstype(fstype: str) -> bool:
    return fstype.lower() in _MKFS


def plan_mount(dev: BlockDevice, mountpoint: str) -> list[list[str]]:
    """Plan to mount *dev* at *mountpoint*.

    Two steps: ``mkdir -p`` so the mount point exists, then ``mount``.  The
    mkdir is safe to run even when the directory is already there.
    """
    return [
        ["mkdir", "-p", mountpoint],
        ["mount", dev.path, mountpoint],
    ]


def plan_unmount(dev: BlockDevice) -> list[list[str]]:
    """Plan to unmount *dev* (lazy unmount so busy filesystems detach cleanly)."""
    return [["umount", "--lazy", dev.path]]


def plan_format(
    dev: BlockDevice,
    fstype: str,
    label: str = "",
) -> list[list[str]]:
    """Plan to format *dev* with *fstype*, optionally setting *label*.

    Raises :exc:`ValueError` for an unknown fstype.  The caller must validate
    that *dev* is unmounted before presenting this plan — diskgrip never
    auto-wipes a live filesystem.
    """
    fstype = fstype.lower()
    if fstype not in _MKFS:
        raise ValueError(
            f"unsupported filesystem type {fstype!r}; "
            f"choose one of: {', '.join(SUPPORTED_FSTYPES)}"
        )
    mkfs = _MKFS[fstype]
    argv: list[str] = [mkfs]
    if label:
        # ext4/btrfs/xfs use -L; vfat/ntfs/exfat use -n.
        flag = "-n" if fstype in ("vfat", "fat32", "ntfs", "exfat") else "-L"
        argv += [flag, label]
    argv.append(dev.path)
    return [argv]


def plan_mount_fstab(
    dev: BlockDevice,
    mountpoint: str,
    fstype: str,
    options: str = "defaults",
) -> list[list[str]]:
    """Plan to add an fstab entry and mount it.

    Appends one line to ``/etc/fstab`` using the device UUID so the entry is
    stable across renames, then mounts via ``mount -a`` which picks up all
    pending fstab entries cleanly.  Uses a shell heredoc so the append is
    atomic (the shell holds the file descriptor open for the whole write).
    """
    uuid = dev.uuid or dev.path  # fall back to path when UUID absent
    fstab_line = f"UUID={uuid}\t{mountpoint}\t{fstype}\t{options}\t0\t2"
    return [
        ["mkdir", "-p", mountpoint],
        ["sh", "-c", f"echo '{fstab_line}' >> /etc/fstab"],
        ["mount", "-a"],
    ]


def plan_create_partition_table(dev: BlockDevice, table_type: str = "gpt") -> list[list[str]]:
    """Plan to write a fresh GPT (or MBR) partition table with parted.

    This wipes the existing partition table.  Requires parted; the caller must
    ensure the device is not in use.
    """
    if table_type not in ("gpt", "msdos"):
        raise ValueError(f"unknown partition table type {table_type!r}; use 'gpt' or 'msdos'")
    return [["parted", "--script", dev.path, "mklabel", table_type]]
