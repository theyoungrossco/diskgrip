"""Parsing of ``lsblk -J -O`` output into the model.

The fixture is trimmed from real ``lsblk -J -O`` output captured on a
util-linux 2.38.1 host (a virtio root disk + a data disk), so the field names
and shapes match what diskgrip actually sees, not a guessed schema.
"""

import json

from diskgrip.core.probe import _clean_mountpoints, parse_lsblk_json

# Faithful to lsblk 2.38.1: note "mountpoints" is a list that holds null for an
# unmounted node, "fsuse%" carries the percent key, and rota/rm/ro are bools.
FIXTURE = {
    "blockdevices": [
        {
            "name": "vda", "type": "disk", "size": "80G", "fstype": None,
            "label": None, "uuid": None, "fsavail": None, "fsuse%": None,
            "mountpoints": [None], "model": None, "serial": None,
            "rota": True, "tran": None, "rm": False, "ro": False,
            "parttypename": None,
            "children": [
                {
                    "name": "vda1", "type": "part", "size": "79.9G",
                    "fstype": "ext4", "fsver": "1.0", "label": None,
                    "uuid": "dac4e68a-047e-42cd-9a9e-33413c3cddf2",
                    "fsavail": "66.8G", "fsuse%": "11%", "mountpoints": ["/"],
                    "rota": True, "tran": None, "rm": False, "ro": False,
                    "parttypename": "Linux root (x86-64)",
                },
                {
                    "name": "vda15", "type": "part", "size": "124M",
                    "fstype": "vfat", "fsver": "FAT32", "label": None,
                    "uuid": "ABCD-1234", "fsavail": "120M", "fsuse%": "3%",
                    "mountpoints": ["/boot/efi"], "rota": True, "tran": None,
                    "rm": False, "ro": False, "parttypename": "EFI System",
                },
            ],
        },
        {
            "name": "vdb", "type": "disk", "size": "250G", "fstype": "ext4",
            "label": "lab", "uuid": "11112222-3333-4444-5555-666677778888",
            "fsavail": "200G", "fsuse%": "20%", "mountpoints": ["/mnt/lab"],
            "rota": True, "tran": None, "rm": False, "ro": False,
            "parttypename": None, "children": [],
        },
    ]
}


def test_top_level_disks_parsed():
    devices = parse_lsblk_json(json.dumps(FIXTURE))
    assert [d.name for d in devices] == ["vda", "vdb"]
    assert all(d.is_disk for d in devices)


def test_unmounted_disk_has_no_mountpoints():
    vda = parse_lsblk_json(json.dumps(FIXTURE))[0]
    # The raw JSON carried mountpoints [null]; that must normalise to empty.
    assert vda.mountpoints == []
    assert vda.mounted is False


def test_partition_fields():
    vda = parse_lsblk_json(json.dumps(FIXTURE))[0]
    root = vda.children[0]
    assert root.name == "vda1"
    assert root.path == "/dev/vda1"
    assert root.is_partition
    assert root.fstype == "ext4"
    assert root.mountpoints == ["/"]
    assert root.fsuse == "11%"
    assert root.parttype == "Linux root (x86-64)"
    assert root.has_filesystem


def test_whole_disk_filesystem():
    vdb = parse_lsblk_json(json.dumps(FIXTURE))[1]
    assert vdb.fstype == "ext4"
    assert vdb.label == "lab"
    assert vdb.mountpoints == ["/mnt/lab"]


def test_walk_yields_every_node():
    devices = parse_lsblk_json(json.dumps(FIXTURE))
    names = [d.name for d in devices for d in d.walk()]
    assert names == ["vda", "vda1", "vda15", "vdb"]


def test_clean_mountpoints_handles_legacy_singular():
    # Pre-2.37 lsblk used a single "mountpoint" string instead of a list.
    assert _clean_mountpoints({"mountpoint": "/data"}) == ["/data"]
    assert _clean_mountpoints({"mountpoint": None}) == []
    assert _clean_mountpoints({"mountpoints": [None, "/a", "/b"]}) == ["/a", "/b"]
