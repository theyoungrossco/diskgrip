"""Canned block-device data for the built-in demo host.

Lets people explore diskgrip (and see the command plans it *would* run)
without root and without touching real storage. Mirrors netgrip's demo host:
the same data path as a live probe, just sourced from here.
"""

from __future__ import annotations

from diskgrip.core.model import BlockDevice

# Byte constants — kept explicit so the proportional gparted bar looks right.
_GiB = 1 << 30
_MiB = 1 << 20


def demo_devices() -> list[BlockDevice]:
    return [
        # Root NVMe SSD: EFI system partition + ext4 root + a swap partition.
        BlockDevice(
            name="nvme0n1", kind="disk", size="476.9G",
            size_bytes=512_000_000_000,
            transport="nvme", rotational=False,
            model="Samsung SSD 980 1TB", serial="S64ANS0T123456",
            pttype="gpt", ptuuid="e3b7c4d1-5f2a-4b8e-9c0d-1a2b3c4d5e6f",
            children=[
                BlockDevice(
                    name="nvme0n1p1", kind="part", size="512.0M",
                    size_bytes=512 * _MiB,
                    start=2048,
                    fstype="vfat", fsver="FAT32", label="EFI",
                    uuid="A1B2-C3D4",
                    fsavail="498.0M", fsuse="2%", mountpoints=["/boot/efi"],
                    parttype="EFI System",
                    partflags=["boot", "esp"],
                ),
                BlockDevice(
                    name="nvme0n1p2", kind="part", size="468.4G",
                    size_bytes=503_316_480_000,
                    start=1_050_624,
                    fstype="ext4", fsver="1.0", label="root",
                    uuid="6f1b2c3d-4e5f-6a7b-8c9d-0e1f2a3b4c5d",
                    fsavail="201.3G", fsuse="52%", mountpoints=["/"],
                    parttype="Linux filesystem",
                ),
                BlockDevice(
                    name="nvme0n1p3", kind="part", size="8.0G",
                    size_bytes=8 * _GiB,
                    start=983_246_848,
                    fstype="swap",
                    uuid="aa11bb22-cc33-dd44-ee55-ff6677889900",
                    mountpoints=["[SWAP]"], parttype="Linux swap",
                    partflags=["swap"],
                ),
            ],
        ),
        # A spinning 4 TB data HDD: one big xfs partition mounted at /srv/data.
        BlockDevice(
            name="sda", kind="disk", size="3.6T",
            size_bytes=3_960_000_000_000,
            transport="sata", rotational=True,
            model="WDC WD40EFRX-68N", serial="WD-WCC7K1234567",
            pttype="gpt", ptuuid="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            children=[
                BlockDevice(
                    name="sda1", kind="part", size="3.6T",
                    size_bytes=3_957_893_120_000,
                    start=2048,
                    fstype="xfs", label="bulk",
                    uuid="1234abcd-5678-90ef-1234-567890abcdef",
                    fsavail="1.1T", fsuse="69%", mountpoints=["/srv/data"],
                    parttype="Linux filesystem",
                ),
            ],
        ),
        # A removable USB stick, partitioned but *not mounted* — a prime
        # candidate for the mount / unmount and (eventually) format plans.
        BlockDevice(
            name="sdb", kind="disk", size="28.9G",
            size_bytes=31_029_321_728,
            transport="usb", rotational=False, removable=True,
            model="SanDisk Ultra Fit", serial="4C530001234567890123",
            pttype="dos", ptuuid="12345678",
            children=[
                BlockDevice(
                    name="sdb1", kind="part", size="28.9G",
                    size_bytes=31_027_224_576,
                    start=2048,
                    fstype="exfat", label="STICK", uuid="DEAD-BEEF",
                    mountpoints=[], parttype="Microsoft basic data",
                ),
            ],
        ),
    ]
