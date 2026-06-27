"""Canned block-device data for the built-in demo host.

Lets people explore diskgrip (and see the command plans it *would* run)
without root and without touching real storage. Mirrors netgrip's demo host:
the same data path as a live probe, just sourced from here.
"""

from __future__ import annotations

from diskgrip.core.model import BlockDevice


def demo_devices() -> list[BlockDevice]:
    return [
        # Root NVMe SSD: EFI system partition + ext4 root + a swap partition.
        BlockDevice(
            name="nvme0n1", kind="disk", size="476.9G", transport="nvme",
            rotational=False, model="Samsung SSD 980 1TB", serial="S64ANS0T123456",
            children=[
                BlockDevice(
                    name="nvme0n1p1", kind="part", size="512M", fstype="vfat",
                    fsver="FAT32", label="EFI", uuid="A1B2-C3D4",
                    fsavail="498M", fsuse="2%", mountpoints=["/boot/efi"],
                    parttype="EFI System",
                ),
                BlockDevice(
                    name="nvme0n1p2", kind="part", size="468.4G", fstype="ext4",
                    fsver="1.0", label="root",
                    uuid="6f1b2c3d-4e5f-6a7b-8c9d-0e1f2a3b4c5d",
                    fsavail="201.3G", fsuse="52%", mountpoints=["/"],
                    parttype="Linux filesystem",
                ),
                BlockDevice(
                    name="nvme0n1p3", kind="part", size="8G", fstype="swap",
                    uuid="aa11bb22-cc33-dd44-ee55-ff6677889900",
                    mountpoints=["[SWAP]"], parttype="Linux swap",
                ),
            ],
        ),
        # A spinning 4 TB data HDD: one big xfs partition mounted at /srv/data.
        BlockDevice(
            name="sda", kind="disk", size="3.6T", transport="sata",
            rotational=True, model="WDC WD40EFRX-68N", serial="WD-WCC7K1234567",
            children=[
                BlockDevice(
                    name="sda1", kind="part", size="3.6T", fstype="xfs",
                    label="bulk", uuid="1234abcd-5678-90ef-1234-567890abcdef",
                    fsavail="1.1T", fsuse="69%", mountpoints=["/srv/data"],
                    parttype="Linux filesystem",
                ),
            ],
        ),
        # A removable USB stick, partitioned but *not mounted* — a prime
        # candidate for the mount / unmount and (eventually) format plans.
        BlockDevice(
            name="sdb", kind="disk", size="28.9G", transport="usb",
            rotational=False, removable=True, model="SanDisk Ultra Fit",
            serial="4C530001234567890123",
            children=[
                BlockDevice(
                    name="sdb1", kind="part", size="28.9G", fstype="exfat",
                    label="STICK", uuid="DEAD-BEEF",
                    mountpoints=[], parttype="Microsoft basic data",
                ),
            ],
        ),
    ]
