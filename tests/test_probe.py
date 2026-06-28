"""Parsing of ``lsblk -J -O`` and ``lsblk -b -J -O`` output into the model.

FIXTURE uses string sizes (pre-``-b`` format); FIXTURE_BYTES uses integer sizes
as returned by ``lsblk -b``, captured from a real util-linux 2.38.1 host
(virtio root disk with three partitions).
"""

import json

from diskgrip.core.probe import _clean_mountpoints, _fmt_bytes, _parse_partflags, parse_lsblk_json

# Legacy format: sizes are human-readable strings (lsblk without -b).
FIXTURE = {
    "blockdevices": [
        {
            "name": "vda", "type": "disk", "size": "80G", "fstype": None,
            "label": None, "uuid": None, "fsavail": None, "fsuse%": None,
            "mountpoints": [None], "model": None, "serial": None,
            "rota": True, "tran": None, "rm": False, "ro": False,
            "parttypename": None, "pttype": "gpt",
            "ptuuid": "1a61acbb-9158-415a-a710-cb0962ae6f4c",
            "children": [
                {
                    "name": "vda1", "type": "part", "size": "79.9G",
                    "fstype": "ext4", "fsver": "1.0", "label": None,
                    "uuid": "dac4e68a-047e-42cd-9a9e-33413c3cddf2",
                    "fsavail": "66.8G", "fsuse%": "11%", "mountpoints": ["/"],
                    "rota": True, "tran": None, "rm": False, "ro": False,
                    "parttypename": "Linux root (x86-64)", "start": 262144,
                    "parttype": "4f68bce3-e8cd-4db1-96e7-fbcaf984b709",
                },
                {
                    "name": "vda15", "type": "part", "size": "124M",
                    "fstype": "vfat", "fsver": "FAT32", "label": None,
                    "uuid": "ABCD-1234", "fsavail": "120M", "fsuse%": "3%",
                    "mountpoints": ["/boot/efi"], "rota": True, "tran": None,
                    "rm": False, "ro": False, "parttypename": "EFI System",
                    "start": 8192,
                    "parttype": "c12a7328-f81f-11d2-ba4b-00a0c93ec93b",
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

# Bytes format: sizes and fsavail are integers (lsblk -b), start in sectors.
# Captured from the test host: vda (80G) with three partitions.
FIXTURE_BYTES = {
    "blockdevices": [
        {
            "name": "vda", "type": "disk", "size": 85899345920, "fstype": None,
            "label": None, "uuid": None, "fsavail": None, "fsuse%": None,
            "mountpoints": [None], "model": None, "serial": None,
            "rota": True, "tran": None, "rm": False, "ro": False,
            "parttypename": None, "pttype": "gpt",
            "ptuuid": "1a61acbb-9158-415a-a710-cb0962ae6f4c",
            "children": [
                {
                    "name": "vda1", "type": "part", "size": 85765111296,
                    "fstype": "ext4", "fsver": "1.0", "label": None,
                    "uuid": "dac4e68a-047e-42cd-9a9e-33413c3cddf2",
                    "fsavail": 70709067776, "fsuse%": "12%",
                    "mountpoints": ["/"], "rota": True, "tran": None,
                    "rm": False, "ro": False, "start": 262144,
                    "parttypename": "Linux root (x86-64)",
                    "parttype": "4f68bce3-e8cd-4db1-96e7-fbcaf984b709",
                },
                {
                    "name": "vda14", "type": "part", "size": 3145728,
                    "fstype": None, "label": None, "uuid": None,
                    "fsavail": None, "fsuse%": None,
                    "mountpoints": [None], "rota": True, "tran": None,
                    "rm": False, "ro": False, "start": 2048,
                    "parttypename": "BIOS boot",
                    "parttype": "21686148-6449-6e6f-744e-656564454649",
                },
                {
                    "name": "vda15", "type": "part", "size": 130023424,
                    "fstype": "vfat", "fsver": "FAT16", "label": None,
                    "uuid": "547A-1B24", "fsavail": 117626880, "fsuse%": "9%",
                    "mountpoints": ["/boot/efi"], "rota": True, "tran": None,
                    "rm": False, "ro": False, "start": 8192,
                    "parttypename": "EFI System",
                    "parttype": "c12a7328-f81f-11d2-ba4b-00a0c93ec93b",
                },
            ],
        },
    ]
}


def test_top_level_disks_parsed():
    devices = parse_lsblk_json(json.dumps(FIXTURE))
    assert [d.name for d in devices] == ["vda", "vdb"]
    assert all(d.is_disk for d in devices)


def test_unmounted_disk_has_no_mountpoints():
    vda = parse_lsblk_json(json.dumps(FIXTURE))[0]
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
    assert _clean_mountpoints({"mountpoint": "/data"}) == ["/data"]
    assert _clean_mountpoints({"mountpoint": None}) == []
    assert _clean_mountpoints({"mountpoints": [None, "/a", "/b"]}) == ["/a", "/b"]


# ── New field tests (pttype, ptuuid, start, partflags) ───────────────────────

def test_pttype_and_ptuuid_parsed():
    vda = parse_lsblk_json(json.dumps(FIXTURE))[0]
    assert vda.pttype == "gpt"
    assert vda.ptuuid == "1a61acbb-9158-415a-a710-cb0962ae6f4c"


def test_start_sector_parsed():
    vda = parse_lsblk_json(json.dumps(FIXTURE))[0]
    root = vda.children[0]  # vda1, start=262144
    assert root.start == 262144
    efi = vda.children[1]   # vda15, start=8192
    assert efi.start == 8192


def test_partflags_efi_system():
    vda = parse_lsblk_json(json.dumps(FIXTURE))[0]
    efi = vda.children[1]  # vda15 — EFI System
    assert "esp" in efi.partflags
    assert "boot" in efi.partflags


def test_partflags_linux_root_empty():
    vda = parse_lsblk_json(json.dumps(FIXTURE))[0]
    root = vda.children[0]  # vda1 — Linux root
    assert root.partflags == []


# ── lsblk -b mode (integer sizes) ────────────────────────────────────────────

def test_bytes_mode_size_parsed_as_int():
    vda = parse_lsblk_json(json.dumps(FIXTURE_BYTES))[0]
    assert vda.size_bytes == 85899345920
    assert vda.size  # formatted, non-empty


def test_bytes_mode_size_formatted():
    vda = parse_lsblk_json(json.dumps(FIXTURE_BYTES))[0]
    assert "G" in vda.size or "T" in vda.size  # ~80 GiB


def test_bytes_mode_fsavail_formatted():
    vda = parse_lsblk_json(json.dumps(FIXTURE_BYTES))[0]
    root = vda.children[0]  # vda1, fsavail=70709067776
    assert root.fsavail  # should be a string like "65.9G"
    assert isinstance(root.fsavail, str)


def test_bytes_mode_partflags_bios_grub():
    vda = parse_lsblk_json(json.dumps(FIXTURE_BYTES))[0]
    bios = next(c for c in vda.children if c.name == "vda14")
    assert "bios_grub" in bios.partflags


def test_bytes_mode_partflags_efi():
    vda = parse_lsblk_json(json.dumps(FIXTURE_BYTES))[0]
    efi = next(c for c in vda.children if c.name == "vda15")
    assert "esp" in efi.partflags


# ── _fmt_bytes ────────────────────────────────────────────────────────────────

def test_fmt_bytes_gib():
    assert _fmt_bytes(85899345920) == "80.0G"


def test_fmt_bytes_mib():
    assert _fmt_bytes(130023424) == "124M"  # ≥100, no decimal


def test_fmt_bytes_small():
    assert _fmt_bytes(3145728) == "3.0M"


def test_fmt_bytes_none():
    assert _fmt_bytes(None) == ""


def test_fmt_bytes_bytes():
    assert _fmt_bytes(512) == "512B"


# ── _parse_partflags ─────────────────────────────────────────────────────────

def test_parse_partflags_by_guid():
    node = {"parttype": "c12a7328-f81f-11d2-ba4b-00a0c93ec93b", "parttypename": None}
    flags = _parse_partflags(node)
    assert "esp" in flags and "boot" in flags


def test_parse_partflags_by_name():
    node = {"parttype": None, "parttypename": "BIOS boot"}
    assert "bios_grub" in _parse_partflags(node)


def test_parse_partflags_empty_for_generic_linux():
    node = {"parttype": "0fc63daf-8483-4772-8e79-3d69d8477de4", "parttypename": "Linux filesystem"}
    assert _parse_partflags(node) == []
