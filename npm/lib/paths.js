"use strict";

const os = require("os");
const path = require("path");

const pkg = require("../package.json");

/**
 * Where downloaded builds are cached, independent of node_modules so a
 * `npm uninstall -g` doesn't strand a locked/running exe, and repeat
 * `npx` invocations don't redownload every time.
 *
 * Windows: %LOCALAPPDATA%\fcc-npm
 * Fallback (dev/testing off-Windows): ~/.cache/fcc-npm
 */
function cacheRoot() {
  if (process.platform === "win32") {
    const base = process.env.LOCALAPPDATA || path.join(os.homedir(), "AppData", "Local");
    return path.join(base, "fcc-npm");
  }
  return path.join(os.homedir(), ".cache", "fcc-npm");
}

function versionDir(version) {
  return path.join(cacheRoot(), "versions", version || pkg.version);
}

function appDir(version) {
  // Matches the folder name PyInstaller's COLLECT(name=...) produces - see
  // windows_tray/build.spec and .github/workflows/build-windows.yml.
  return path.join(versionDir(version), "Free Claude Code");
}

function exePath(version) {
  return path.join(appDir(version), "Free Claude Code.exe");
}

function downloadTmpZipPath(version) {
  return path.join(cacheRoot(), `download-${version || pkg.version}.zip`);
}

module.exports = { cacheRoot, versionDir, appDir, exePath, downloadTmpZipPath };
