"use strict";

const http = require("http");
const { spawn, execFile } = require("child_process");

const EXE_PROCESS_NAME = "Free Claude Code.exe";
const DEFAULT_ADMIN_URL = "http://127.0.0.1:8082/admin";
const DEFAULT_HEALTH_URL = "http://127.0.0.1:8082/health";

/**
 * Launch the exe fully detached from this Node process, so it keeps running
 * after `fcc start` returns - including after the terminal that ran it is
 * closed. The exe's own single-instance mutex (windows_tray/tray_app.py)
 * makes this safe to call even when an instance is already running: the
 * new process just notices the mutex, opens the admin UI, and exits.
 */
function launchDetached(exePath) {
  const child = spawn(exePath, [], {
    detached: true,
    stdio: "ignore",
    windowsHide: true,
  });
  child.unref();
}

function httpGetOk(url, timeoutMs) {
  return new Promise((resolve) => {
    const req = http.get(url, { timeout: timeoutMs }, (res) => {
      res.resume();
      resolve(res.statusCode >= 200 && res.statusCode < 400);
    });
    req.on("timeout", () => {
      req.destroy();
      resolve(false);
    });
    req.on("error", () => resolve(false));
  });
}

/** Poll the health endpoint a few times so `fcc start` can report readiness. */
async function waitUntilReady(healthUrl, { attempts = 40, intervalMs = 250 } = {}) {
  for (let i = 0; i < attempts; i += 1) {
    // eslint-disable-next-line no-await-in-loop
    if (await httpGetOk(healthUrl, 1000)) {
      return true;
    }
    // eslint-disable-next-line no-await-in-loop
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  return false;
}

function isRunning(healthUrl) {
  return httpGetOk(healthUrl || DEFAULT_HEALTH_URL, 1000);
}

/**
 * Open a URL with the OS default handler. Errors are swallowed on purpose
 * (falling back to just printing the URL) - failing to auto-open a browser
 * is never worth crashing the CLI over, and a completely missing/broken
 * `cmd.exe` is not something worth surfacing loudly.
 */
function openInBrowser(url) {
  if (process.platform !== "win32") {
    console.log(`Open manually: ${url}`);
    return;
  }
  const child = execFile("cmd", ["/c", "start", "", url], () => {});
  child.on("error", () => {
    console.log(`Open manually: ${url}`);
  });
}

/**
 * Convenience CLI stop. The intended/primary way to stop is still the tray
 * icon's own Quit item - this exists for scripting/dev-loop convenience and
 * is a plain best-effort taskkill, nothing fancier.
 */
function stopViaTaskkill() {
  return new Promise((resolve) => {
    execFile("taskkill", ["/IM", EXE_PROCESS_NAME, "/F"], (err) => {
      resolve(!err);
    });
  });
}

module.exports = {
  EXE_PROCESS_NAME,
  DEFAULT_ADMIN_URL,
  DEFAULT_HEALTH_URL,
  launchDetached,
  isRunning,
  waitUntilReady,
  openInBrowser,
  stopViaTaskkill,
};
