"""System tray wrapper for the Free Claude Code proxy (Windows).

What this does:
  - Runs the existing ``cli.entrypoints.serve()`` FastAPI/uvicorn server in a
    background thread (unmodified - inherits its config migration, admin
    auto-restart support, and auto-open-browser-on-ready behavior for free).
  - Shows a system tray icon with "Open Admin UI" and "Quit".
  - Enforces a single running instance: launching the exe again while it's
    already running just opens the admin UI in your browser instead of
    starting a second server (which would fail to bind the port anyway).
  - Keeps running until you choose Quit from the tray menu, or Windows ends
    the process at logoff/shutdown/restart - both are ordinary process
    lifecycle, nothing special is needed for the shutdown/restart case.

Run from source for development:
    python windows_tray/tray_app.py

Package it into Free Claude Code.exe:
    windows_tray\\build.bat
"""

from __future__ import annotations

import sys
import threading
import time
import webbrowser
from pathlib import Path

# --------------------------------------------------------------------------
# Make the free-claude-code package importable when run from source. Under
# a PyInstaller build (``sys.frozen``) everything is already on sys.path by
# the bootloader, so this is a no-op there.
# --------------------------------------------------------------------------
if not getattr(sys, "frozen", False):
    _repo_root = Path(__file__).resolve().parent.parent
    if str(_repo_root) not in sys.path:
        sys.path.insert(0, str(_repo_root))

APP_NAME = "Free Claude Code"
_MUTEX_NAME = "Global\\FreeClaudeCodeTray_SingleInstanceMutex"
_ERROR_ALREADY_EXISTS = 183


def _acquire_single_instance_lock() -> bool:
    """Return True if this is the only running instance.

    Uses a named Windows mutex via raw ctypes (no pywin32 dependency). The
    mutex handle is intentionally never closed - it's released automatically
    when this process exits, which is exactly when we want the "instance"
    to stop counting as running.
    """
    if sys.platform != "win32":
        # Non-Windows dev environments (e.g. testing tray_app.py's logic on
        # Linux/macOS before a Windows packaging pass): don't block startup.
        return True
    import ctypes

    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    return kernel32.GetLastError() != _ERROR_ALREADY_EXISTS


def _admin_url() -> str:
    from api.admin_urls import local_admin_url
    from config.settings import get_settings

    return local_admin_url(get_settings())


def _open_admin(icon=None, item=None) -> None:  # noqa: ANN001 - pystray callback signature
    webbrowser.open(_admin_url())


def _run_server() -> None:
    from cli.entrypoints import serve

    serve()


def _start_server_thread() -> threading.Thread:
    thread = threading.Thread(target=_run_server, name="fcc-server", daemon=True)
    thread.start()
    return thread


def _watch_for_server_crash(icon, server_thread: threading.Thread) -> None:  # noqa: ANN001
    """Flip the tray icon to an error state if the server thread dies unexpectedly."""
    server_thread.join()
    if getattr(icon, "_quitting", False):
        return  # normal shutdown, not a crash
    try:
        icon.title = f"{APP_NAME} - server stopped unexpectedly (see logs)"
        icon.notify(
            "The proxy server stopped unexpectedly. Check ~/.fcc/logs for details.",
            APP_NAME,
        )
    except Exception:
        pass  # notifications are best-effort; never let this thread crash the icon


def _quit(icon, item=None) -> None:  # noqa: ANN001
    icon._quitting = True
    icon.stop()


def _build_menu():
    import pystray

    return pystray.Menu(
        pystray.MenuItem("Open Admin UI", _open_admin, default=True),
        pystray.MenuItem("Quit", _quit),
    )


def _load_icon_image():
    from PIL import Image

    ico_path = Path(__file__).resolve().parent / "app.ico"
    if ico_path.is_file():
        return Image.open(ico_path)
    # Fallback so a from-source run works even before generate_icon.py has
    # been run once - a plain filled square is enough to be visible.
    return Image.new("RGBA", (64, 64), (214, 108, 58, 255))


def main() -> None:
    import pystray

    if not _acquire_single_instance_lock():
        _open_admin()
        return

    server_thread = _start_server_thread()

    icon = pystray.Icon(APP_NAME, _load_icon_image(), APP_NAME, _build_menu())
    icon._quitting = False

    threading.Thread(
        target=_watch_for_server_crash,
        args=(icon, server_thread),
        name="fcc-server-watchdog",
        daemon=True,
    ).start()

    icon.run()


if __name__ == "__main__":
    main()
