# free-claude-code (`fcc`)

Run the Free Claude Code proxy as a background service with a system tray
icon, via `fcc start` - no Python install, no manual setup on the machine
running it.

```
npx free-claude-code start
# or, once installed globally, just:
npm i -g free-claude-code
fcc start
```

Note the package name is `free-claude-code` (`fcc` was already taken on the
npm registry) but the installed **command** is `fcc` either way - that's
what `"bin"` in package.json controls, independent of the package name.
`npx free-claude-code start` works today; a bare `npx fcc` would fetch
someone else's unrelated package, so it's not used here.

## How this actually works

This package is **not** a reimplementation of the proxy in JavaScript - the
server is, and stays, Python. Node can't run Python code directly, and a
`postinstall` script that shells out to `pip install` on whatever Python the
user happens to have is fragile (wrong version, missing Python entirely,
permission issues, conflicts with their other envs) - especially since this
project specifically needs Python 3.14+.

So instead, this package is a **thin launcher**:

1. `windows_tray/` (see the repo root) already builds a fully self-contained
   Windows app with PyInstaller - Python interpreter and all dependencies
   bundled into one folder, system tray icon included via `pystray`. No
   separate Python install needed on the end user's machine at all.
2. `.github/workflows/build-windows.yml` builds that on a real Windows
   GitHub Actions runner and publishes it as a GitHub Release asset
   (`FreeClaudeCode-windows.zip`) whenever you push a `v*` tag.
3. `fcc start` downloads that release asset once (cached under
   `%LOCALAPPDATA%\fcc-npm`), then spawns it **detached** so it keeps
   running after the terminal closes - stopping only via the tray icon's
   Quit (or `fcc stop` as a scripting convenience).

Re-running `fcc start` while it's already running doesn't start a second
copy: the exe's own single-instance mutex (`windows_tray/tray_app.py`)
handles that and just reopens the Admin UI.

## Before publishing this package

Edit `lib/github.js` and set `REPO_OWNER` to your own GitHub username (the
download URL has to point at *your* fork/repo - the upstream
`Alishahryar1/free-claude-code` doesn't have the tray app, multi-key
pooling, or Kilo Gateway support this build includes). Then:

```
git tag v1.0.0
git push origin v1.0.0        # triggers build-windows.yml, publishes the Release
cd npm
npm publish                   # publishes the launcher package itself
```

The two version numbers (`npm/package.json`'s `version` and the git tag)
need to stay in sync - `lib/github.js` builds the download URL from
whichever one is currently installed.

## Commands

| Command | Does |
|---|---|
| `fcc` / `fcc start` | Download (first time only) + launch in the background, wait for it to become healthy, print the Admin UI URL. |
| `fcc status` | Check whether it's currently reachable. |
| `fcc open` | Just open the Admin UI in your browser. |
| `fcc stop` | Convenience `taskkill`-based stop. The tray icon's Quit remains the primary way. |

## Current scope: Windows only

`windows_tray/` and this launcher both currently target Windows 10+ only,
matching how the tray app was originally scoped. `fcc start`/`stop` print a
clear message and exit non-zero on macOS/Linux rather than doing anything
silently wrong. Extending to other platforms means adding
`macos-latest`/`ubuntu-latest` jobs to `build-windows.yml` (PyInstaller and
pystray both support those) and a matching per-platform asset name/URL in
`lib/github.js` - the launcher's structure doesn't need to change.
