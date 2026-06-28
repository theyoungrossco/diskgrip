"""Tests for display detection and GUI/CLI dispatch — pure, no Qt."""

from diskgrip.core.display import choose_gui, has_display

# ---------------------------------------------------------------------------
# has_display
# ---------------------------------------------------------------------------

def test_has_display_x11(monkeypatch):
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    assert has_display() is True


def test_has_display_wayland(monkeypatch):
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    assert has_display() is True


def test_has_display_both(monkeypatch):
    monkeypatch.setenv("DISPLAY", ":1")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-1")
    assert has_display() is True


def test_has_display_headless(monkeypatch):
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    assert has_display() is False


def test_has_display_offscreen_env_does_not_count(monkeypatch):
    """QT_QPA_PLATFORM=offscreen alone must not be treated as a display."""
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    assert has_display() is False


# ---------------------------------------------------------------------------
# choose_gui
# ---------------------------------------------------------------------------

def test_choose_gui_force_gui_overrides_headless(monkeypatch):
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    assert choose_gui(force_gui=True) is True


def test_choose_gui_force_cli_overrides_display(monkeypatch):
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    assert choose_gui(force_cli=True) is False


def test_choose_gui_autodetect_with_display(monkeypatch):
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    assert choose_gui() is True


def test_choose_gui_autodetect_headless(monkeypatch):
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    assert choose_gui() is False
