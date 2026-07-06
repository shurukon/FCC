# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Free Claude Code tray app (Windows).

Build with (from the repo root, inside a Windows Python 3.14 venv with the
project's own dependencies installed - see windows_tray/build.bat):

    pyinstaller windows_tray/build.spec --noconfirm

This MUST be run on Windows: PyInstaller bundles whatever is installed in
the *current* venv, it does not cross-compile. Running it on Linux/macOS
would bundle Linux/macOS native wheels (pydantic-core, tiktoken, aiohttp,
...) into something that cannot run on Windows.
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

REPO_ROOT = Path(SPECPATH).resolve().parent

block_cipher = None

# tiktoken's per-encoding modules (tiktoken_ext.openai_public) are loaded
# through a namespace-package plugin mechanism that PyInstaller's static
# import analysis does not see - without this, a packaged build fails at
# runtime with "Unknown encoding cl100k_base" the first time a request
# needs to count tokens.
hidden_imports = [
    *collect_submodules("tiktoken_ext"),
    "tiktoken_ext.openai_public",
    # uvicorn selects its event loop / HTTP protocol implementation at
    # runtime; make sure both are bundled regardless of what the build
    # machine's own default happens to resolve to.
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.wsproto_impl",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    "uvicorn.logging",
    # Messaging integrations import their platform SDKs dynamically enough
    # in places that it's worth pinning them explicitly too.
    "discord",
    "telegram",
    "telegram.ext",
]

datas = [
    # The Admin UI is plain static HTML/CSS/JS served from disk by
    # api/admin_routes.py - PyInstaller only auto-bundles Python modules,
    # so these need to be listed explicitly or /admin 404s in the exe.
    (str(REPO_ROOT / "api" / "admin_static"), "api/admin_static"),
    # Fallback template read by `fcc-init`/first-run config scaffolding
    # (config/env_template.py) when no packaged config-package resource is
    # found - see that module for the lookup order.
    (str(REPO_ROOT / ".env.example"), "."),
    # NOTE: EXE(icon=...) below only sets the *compiled exe file's own* PE
    # icon resource (Explorer/taskbar) - it does not make app.ico readable
    # as a plain file at runtime. tray_app.py's _load_icon_image() opens it
    # as a file for the actual system tray icon, so it needs its own datas
    # entry too, or the tray icon silently falls back to a plain square
    # while the exe's Explorer icon looks fine - a real, easy-to-miss gap.
    (str(REPO_ROOT / "windows_tray" / "app.ico"), "windows_tray"),
]

a = Analysis(
    [str(REPO_ROOT / "windows_tray" / "tray_app.py")],
    pathex=[str(REPO_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Heavy optional extras (see pyproject.toml [project.optional-dependencies])
        # that most users won't have installed and don't need in the tray build.
        "torch",
        "transformers",
        "grpc",
        "nvidia_riva_client",
    ],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Free Claude Code",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # tray app: no console window
    icon=str(REPO_ROOT / "windows_tray" / "app.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="Free Claude Code",
)
