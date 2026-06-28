"""Data model describing the block-storage state of one host.

These classes are plain data carriers. They are produced by
:mod:`diskgrip.core.probe` and consumed by the UI / CLI; they never talk to
the system themselves. This mirrors netgrip's ``core/model.py``: pure Python,
no Qt, headless-testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# lsblk "type" values we treat as a whole-disk root (something you'd partition).
DISK_KINDS = {"disk", "loop"}
# Kinds that sit *on* a disk and usually carry a filesystem.
LEAF_KINDS = {"part", "lvm", "crypt", "raid0", "raid1", "raid5", "raid6", "raid10"}
# Pseudo filesystems that aren't really "on a disk" — hidden from the topology.
PSEUDO_FSTYPES = {"swap"}


@dataclass
class BlockDevice:
    """One node of the block-device tree as reported by ``lsblk``.

    lsblk is recursive (a disk holds partitions, a partition may hold an LVM or
    LUKS mapping), so this one dataclass models every level; ``children`` nests
    the same type. Sizes are kept as lsblk's human strings ("80G", "124M") for
    faithful display — diskgrip is a *viewer first*, and never does size
    arithmetic on a guessed byte count.
    """

    name: str  # bare kernel name, e.g. "vda1" (no /dev/)
    kind: str  # lsblk "type": disk | part | loop | rom | lvm | crypt | raid* ...
    size: str = ""  # human-readable, as lsblk prints it
    fstype: str | None = None  # ext4, xfs, vfat, swap, LVM2_member, crypto_LUKS …
    fsver: str | None = None
    label: str | None = None  # filesystem label
    uuid: str | None = None
    fsavail: str | None = None  # human-readable free space (mounted fs only)
    fsuse: str | None = None  # used percentage as lsblk prints it, e.g. "11%"
    mountpoints: list[str] = field(default_factory=list)  # Nones dropped
    model: str | None = None  # disk model string
    serial: str | None = None
    rotational: bool | None = None  # lsblk "rota": True spinning, False solid-state
    transport: str | None = None  # lsblk "tran": sata | nvme | usb | …
    parttype: str | None = None  # human partition type, lsblk "parttypename"
    removable: bool = False  # lsblk "rm"
    readonly: bool = False  # lsblk "ro"
    size_bytes: int | None = None  # raw byte count from lsblk -b; None when probing without -b
    start: int | None = None  # partition start in sectors (lsblk "start")
    partflags: list[str] = field(default_factory=list)  # ["esp", "boot", "bios_grub", "lvm", ...]
    pttype: str | None = None  # partition table type at disk level: "gpt" | "dos" | None
    ptuuid: str | None = None  # partition table UUID
    children: list[BlockDevice] = field(default_factory=list)

    @property
    def path(self) -> str:
        """The /dev path you'd hand to mount, mkfs, etc."""
        return f"/dev/{self.name}"

    @property
    def is_disk(self) -> bool:
        return self.kind in DISK_KINDS

    @property
    def is_partition(self) -> bool:
        return self.kind == "part"

    @property
    def mounted(self) -> bool:
        return bool(self.mountpoints)

    @property
    def is_swap(self) -> bool:
        return self.fstype == "swap"

    @property
    def has_filesystem(self) -> bool:
        """A mountable filesystem lives here (not empty, not a container layer)."""
        if not self.fstype:
            return False
        return self.fstype not in ("LVM2_member", "crypto_LUKS")

    @property
    def media(self) -> str:
        """Coarse media class for themed display, derived from transport/rotation.

        One of: ``usb``, ``optical``, ``ssd``, ``hdd``, ``virtual`` or
        ``unknown``. Best-effort — virtual disks report no transport and often
        ``rota: true`` even when backed by SSD, so they get their own bucket.
        """
        if self.kind == "rom":
            return "optical"
        if self.transport == "usb":
            return "usb"
        if self.transport == "nvme":
            return "ssd"
        if self.name.startswith(("vd", "xvd")) or self.transport == "virtio":
            return "virtual"
        if self.rotational is True:
            return "hdd"
        if self.rotational is False:
            return "ssd"
        return "unknown"

    def label_text(self) -> str:
        """Short human label: the fs label, else the mountpoint, else the name."""
        if self.label:
            return self.label
        if self.mountpoints:
            return self.mountpoints[0]
        return self.name

    def walk(self):
        """Yield this device and every descendant, depth-first."""
        yield self
        for child in self.children:
            yield from child.walk()
