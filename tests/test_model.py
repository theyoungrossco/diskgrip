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


def test_new_accuracy_fields_have_sane_defaults():
    dev = BlockDevice("sda", "disk")
    assert dev.size_bytes is None
    assert dev.start is None
    assert dev.partflags == []
    assert dev.pttype is None
    assert dev.ptuuid is None


def test_partflags_stored_and_walked():
    disk = BlockDevice(
        "nvme0n1", "disk", size_bytes=512_000_000_000, pttype="gpt",
        children=[
            BlockDevice("nvme0n1p1", "part", size_bytes=536_870_912,
                        start=2048, partflags=["boot", "esp"]),
            BlockDevice("nvme0n1p2", "part", size_bytes=503_316_480_000,
                        start=1_050_624),
        ],
    )
    efi = disk.children[0]
    assert "esp" in efi.partflags
    assert efi.start == 2048
    assert disk.size_bytes == 512_000_000_000
    assert disk.pttype == "gpt"
    names = [d.name for d in disk.walk()]
    assert names == ["nvme0n1", "nvme0n1p1", "nvme0n1p2"]
