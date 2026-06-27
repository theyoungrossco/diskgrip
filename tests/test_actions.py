"""Unit tests for core/actions.py — plan shapes, not execution."""

import pytest

from diskgrip.core.actions import (
    plan_create_partition_table,
    plan_format,
    plan_mount,
    plan_mount_fstab,
    plan_unmount,
    valid_fstype,
    valid_mountpoint,
)
from diskgrip.core.model import BlockDevice

_USB = BlockDevice("sdb1", "part", fstype="exfat", uuid="DEAD-BEEF")
_NVME = BlockDevice("nvme0n1p2", "part", fstype="ext4", uuid="6f1b2c3d-0000-0000-0000-000000000000")
_DISK = BlockDevice("sda", "disk")


# ------------------------------------------------------------------
# validators
# ------------------------------------------------------------------

def test_valid_mountpoint_accepts_absolute():
    assert valid_mountpoint("/mnt/usb")
    assert valid_mountpoint("/srv/data")


def test_valid_mountpoint_rejects_root_and_relative():
    assert not valid_mountpoint("/")
    assert not valid_mountpoint("mnt/usb")
    assert not valid_mountpoint("")


def test_valid_fstype():
    assert valid_fstype("ext4")
    assert valid_fstype("XFS")  # case-insensitive
    assert not valid_fstype("iso9660")
    assert not valid_fstype("")


# ------------------------------------------------------------------
# plan_mount
# ------------------------------------------------------------------

def test_plan_mount_creates_dir_then_mounts():
    plan = plan_mount(_USB, "/mnt/stick")
    assert plan == [
        ["mkdir", "-p", "/mnt/stick"],
        ["mount", "/dev/sdb1", "/mnt/stick"],
    ]


# ------------------------------------------------------------------
# plan_unmount
# ------------------------------------------------------------------

def test_plan_unmount_is_lazy_umount():
    plan = plan_unmount(_USB)
    assert plan == [["umount", "--lazy", "/dev/sdb1"]]


# ------------------------------------------------------------------
# plan_format
# ------------------------------------------------------------------

def test_plan_format_ext4_no_label():
    plan = plan_format(_USB, "ext4")
    assert plan == [["mkfs.ext4", "/dev/sdb1"]]


def test_plan_format_ext4_with_label():
    plan = plan_format(_USB, "ext4", label="backups")
    assert plan == [["mkfs.ext4", "-L", "backups", "/dev/sdb1"]]


def test_plan_format_vfat_uses_n_flag():
    plan = plan_format(_USB, "vfat", label="BOOT")
    assert plan == [["mkfs.vfat", "-n", "BOOT", "/dev/sdb1"]]


def test_plan_format_xfs_with_label():
    plan = plan_format(_USB, "xfs", label="data")
    assert plan == [["mkfs.xfs", "-L", "data", "/dev/sdb1"]]


def test_plan_format_btrfs_no_label():
    plan = plan_format(_USB, "btrfs")
    assert plan == [["mkfs.btrfs", "/dev/sdb1"]]


def test_plan_format_unknown_fstype_raises():
    with pytest.raises(ValueError, match="unsupported"):
        plan_format(_USB, "iso9660")


def test_plan_format_case_insensitive():
    plan = plan_format(_USB, "EXT4")
    assert plan[0][0] == "mkfs.ext4"


# ------------------------------------------------------------------
# plan_mount_fstab
# ------------------------------------------------------------------

def test_plan_mount_fstab_uses_uuid():
    plan = plan_mount_fstab(_NVME, "/mnt/data", "ext4")
    fstab_cmd = plan[1]
    assert "UUID=6f1b2c3d-0000-0000-0000-000000000000" in fstab_cmd[-1]
    assert "/mnt/data" in fstab_cmd[-1]
    assert "ext4" in fstab_cmd[-1]


def test_plan_mount_fstab_falls_back_to_path_when_no_uuid():
    dev = BlockDevice("sdc1", "part", fstype="xfs")
    plan = plan_mount_fstab(dev, "/srv", "xfs")
    fstab_cmd = plan[1]
    assert "UUID=/dev/sdc1" in fstab_cmd[-1]


def test_plan_mount_fstab_ends_with_mount_a():
    plan = plan_mount_fstab(_NVME, "/mnt/data", "ext4")
    assert plan[-1] == ["mount", "-a"]


# ------------------------------------------------------------------
# plan_create_partition_table
# ------------------------------------------------------------------

def test_plan_create_gpt():
    plan = plan_create_partition_table(_DISK)
    assert plan == [["parted", "--script", "/dev/sda", "mklabel", "gpt"]]


def test_plan_create_msdos():
    plan = plan_create_partition_table(_DISK, "msdos")
    assert plan == [["parted", "--script", "/dev/sda", "mklabel", "msdos"]]


def test_plan_create_unknown_table_raises():
    with pytest.raises(ValueError, match="unknown partition table"):
        plan_create_partition_table(_DISK, "bsd")
