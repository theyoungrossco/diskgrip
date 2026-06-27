# DiskGrip roadmap

DiskGrip is the block-storage sibling of [netgrip](../../netgrip): probe the
host, model it as plain dataclasses, and turn every change into an explicit
command *plan* the user confirms before anything runs. Destructive operations
(format, partition-table wipe) are never auto-executed.

This is a direction, not a contract. Same shape of work as netgrip: keep `core/`
headless and Qt-free, keep mutations plan-first, ship one focused capability at
a time.

## Shipped

- **0.0.1 — scaffold.** Read-only probe (`lsblk -J -O` → `parse_lsblk_json()` →
  `list[BlockDevice]`), the dataclass model, the plan functions (mount, unmount,
  format, fstab mount, create partition table), a vendored SSH/local runner, and
  a terminal viewer (`diskgrip --demo` / live / `--host`). A first PySide6 canvas
  layer also landed.

## Next

### Canvas — gparted-style, partitions *inside* the disk

The defining visual decision: **partitions are drawn nested inside their disk,
not as separate boxes wired to it.** GParted is the reference and it's close to
right — match it:

- each **disk** is a horizontal bar; its **partitions are proportional segments
  *inside* that bar** (segment width ∝ size), in on-disk order;
- **unallocated space** is its own segment, not a gap;
- **extended / logical** partitions nest one level deeper inside the extended
  segment;
- **no connector lines** between a disk and its own partitions — containment
  expresses the relationship (connectors are reserved for cross-device links
  like LVM PV→VG→LV, RAID members, or a mapped/encrypted device → its backing
  partition, which *do* span devices).

This keeps DiskGrip's "flat, themed" look (colours from the theme module, never
hardcoded) while reading instantly to anyone who knows GParted.

### Accuracy as a first-class goal

GParted sets the bar for correctness; DiskGrip should match it. A dedicated
accuracy pass, cross-checked against `gparted` / `lsblk -b` / `blkid` on real
hardware and pinned with captured fixtures:

- partition **sizes and offsets** (byte-accurate, not rounded-only);
- **filesystem type + label**, and **used vs free** where the FS can report it;
- **flags** (boot / esp / bios_grub / lvm / raid / swap);
- sector size, partition-table type (GPT/MBR), and alignment.

### GUI by default when there's a display

Shared with netgrip: the bare `diskgrip` command should **launch the GUI when a
display is available** and fall back to the terminal viewer when headless — with
explicit `--gui` / `--cli` overrides. Detect via `DISPLAY` / `WAYLAND_DISPLAY`
plus a cheap Qt platform probe; the headless path must never try to spawn a GUI,
and `QT_QPA_PLATFORM=offscreen` must still work for tests.

### Mutations — carefully, plan-first

The plans already exist; surfacing them in the canvas comes after read-only
clarity is solid. Every destructive op (format, mklabel, partition create/delete,
resize) is shown as exact commands and confirmed first; a "Try" that's safe to
abort is the long-term goal where the operation allows it. Resize/move is the
hard, dangerous frontier — last, and only with strong tests.

## Shared toolkit with netgrip

Both tools are the same skeleton — *probe real state → dataclasses → plan-first
mutations → flat themed canvas, GUI-or-CLI*. The runner, theme and plan-confirm
layers are duplicated today and want to converge into a shared package once both
have settled. Until then, keep the patterns deliberately parallel so the merge
is mechanical later.
