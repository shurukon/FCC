# Free Claude Code - Windows tray app

Wraps the existing proxy server in a system tray icon: launches it in the
background, opens the Admin UI in your browser, and keeps running until you
Quit from the tray menu or Windows shuts down/restarts. Launching the exe
again while it's already running just reopens the Admin UI instead of
starting a second server.

## Option A - build locally (fastest, one command)

Needs: Python 3.14+ on PATH. Optional: [Inno Setup 6](https://jrsoftware.org/isinfo.php)
for the full installer; without it you still get a working raw exe.

```
windows_tray\build.bat
```

Output:
- `dist\Free Claude Code\Free Claude Code.exe` - always produced.
- `windows_tray\installer_output\FreeClaudeCodeSetup.exe` - only if Inno Setup is installed.

## Option B - build on GitHub (no Windows machine needed)

Push this repo to GitHub, then run the **Build Windows tray app** workflow
from the Actions tab (or push a `v*` tag). It builds on a real GitHub-hosted
Windows runner and uploads both the raw app and the installer as downloadable
artifacts on the run page. See `.github/workflows/build-windows.yml`.

## Files

| File | Purpose |
|---|---|
| `tray_app.py` | The tray app itself - entry point for both dev runs and the packaged exe. |
| `generate_icon.py` | Generates `app.ico` (a plain generated monogram - swap in your own art anytime). |
| `build.spec` | PyInstaller spec: what gets bundled, hidden imports, icon. |
| `installer.iss` | Inno Setup script: shortcuts, optional "start with Windows", uninstaller. |
| `build.bat` | Runs all of the above in one command. |

## Notes

- First launch needs internet briefly: `tiktoken` downloads its ~1.7MB
  tokenizer data file on first use and caches it under your user profile -
  same as running from source, nothing packaging-specific.
- Config lives at `%USERPROFILE%\.fcc\.env` regardless of where the exe is
  installed - the Admin UI writes there.
- `PrivilegesRequired=lowest` in `installer.iss` means no UAC prompt and a
  per-user install (`%LocalAppData%\Programs\Free Claude Code`). Change it
  to `admin` + swap `{autopf}` for `{commonpf}` if you'd rather install for
  all users on the machine.
