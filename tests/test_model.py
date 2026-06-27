"""Behaviour of the BlockDevice model (media classification, helpers)."""

from diskgrip.core.model import BlockDevice


def test_media_classification():
    assert BlockDevice("nvme0n1", "disk", transport="nvme").media == "ssd"
    assert BlockDevice("sda", "disk", transport="sata", rotational=True).media == "hdd"
    assert BlockDevice("sdb", "disk", transport="usb").media == "usb"
    assert BlockDevice("sr0", "rom").media == "optical"
    assert BlockDevice("vda", "disk", rotational=True).media == "virtual"
    assert BlockDevice("md0", "disk").media == "unknown"


def test_has_filesystem_excludes_container_layers():
    assert BlockDevice("p1", "part", fstype="ext4").has_filesystem
    assert not BlockDevice("p2", "part", fstype="LVM2_member").has_filesystem
    assert not BlockDevice("p3", "part", fstype="crypto_LUKS").has_filesystem
    assert not BlockDevice("p4", "part").has_filesystem


def test_label_text_prefers_label_then_mount_then_name():
    assert BlockDevice("p1", "part", label="data").label_text() == "data"
    assert BlockDevice("p2", "part", mountpoints=["/srv"]).label_text() == "/srv"
    assert BlockDevice("p3", "part").label_text() == "p3"


def test_swap_and_path():
    swap = BlockDevice("p1", "part", fstype="swap", mountpoints=["[SWAP]"])
    assert swap.is_swap
    assert swap.path == "/dev/p1"
