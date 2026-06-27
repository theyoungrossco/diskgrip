# diskgrip

Visual block-storage management for Linux — a sibling to [netgrip](../netgrip).

Same philosophy: probe the host, model it as plain dataclasses, and turn every
change into an explicit command *plan* that the user confirms before anything
runs. Destructive disk operations (format, partition-table wipe) are **never
auto-executed**.

## Architecture

```
lsblk -J -O        (read-only probe)
  → core.probe.parse_lsblk_json()   pure parser → list[BlockDevice]
  → core.actions.plan_*()           build argv lists, pure, testable
  → confirm dialog                  user sees the exact commands
  → core.runner.run_privileged()    one escalated sh -c batch
  → re-probe → redraw
```

Two layers:

- **`src/diskgrip/core/`** — plain Python, no Qt. Probes with `lsblk -J`,
  holds the result in dataclasses (`model.py`), builds command plans
  (`actions.py`). Headless-testable without PySide6 installed.
- **`src/diskgrip/ui/`** — PySide6 canvas *(planned for a later session)*.

## Quick start

```sh
cd ~/diskgrip
python -m venv .venv && pip install -e ".[dev]"

diskgrip --demo        # canned demo host, no root, touches nothing
diskgrip               # probe this machine's block devices (read-only)
diskgrip --host HOST   # read a remote host over SSH

.venv/bin/pytest                # core unit tests (no Qt needed)
.venv/bin/ruff check src tests  # lint
```

## Hard rules

1. **`core/` never imports Qt.** Tests run without PySide6.
2. **Every mutation is a plan first.** A change is a `plan_*()` in
   `core/actions.py` returning `list[list[str]]`. Nothing runs until the user
   confirms the exact commands.
3. **One batch per user action.** `Runner.run_privileged()` joins a plan with
   `&&` into a single `sh -c`.
4. **Never auto-execute destructive ops.** Format and partition-table creation
   are always shown and confirmed first.

## Supported operations (core)

| Plan function | Commands |
|---|---|
| `plan_mount(dev, mountpoint)` | `mkdir -p`, `mount` |
| `plan_unmount(dev)` | `umount --lazy` |
| `plan_format(dev, fstype, label)` | `mkfs.<fstype>` |
| `plan_mount_fstab(dev, mountpoint, fstype)` | append to `/etc/fstab`, `mount -a` |
| `plan_create_partition_table(dev, type)` | `parted mklabel` |

## Status

`0.0.1` — scaffold session. Core probe + model + actions complete. CLI viewer
(`diskgrip --demo`) works. PySide6 canvas is the next session.
