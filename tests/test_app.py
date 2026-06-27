"""The headless tree renderer and the demo path."""

from diskgrip.app import main, render_tree
from diskgrip.core.demo import demo_devices


def test_render_demo_tree_has_disks_and_partitions():
    out = render_tree(demo_devices())
    assert "nvme0n1" in out
    assert "nvme0n1p2" in out
    # A mounted partition shows where it lives; the USB stick shows unmounted.
    assert "→ /" in out
    assert "(not mounted)" in out


def test_render_empty():
    assert render_tree([]) == "(no block devices found)"


def test_demo_main_runs_clean(capsys):
    rc = main(["--demo"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "demo host" in out
    assert "nothing is executed" in out
