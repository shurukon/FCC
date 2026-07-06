#!/usr/bin/env node
"use strict";

const { ensureDownloaded } = require("../lib/download");
const {
  DEFAULT_ADMIN_URL,
  DEFAULT_HEALTH_URL,
  launchDetached,
  isRunning,
  waitUntilReady,
  openInBrowser,
  stopViaTaskkill,
} = require("../lib/process");

const HELP = `
fcc - Free Claude Code proxy, as a background service + system tray icon.

Usage:
  fcc [start]   Start it in the background if not already running, then
                open the Admin UI (http://127.0.0.1:8082/admin by default).
                Keeps running after this terminal closes - stop it from the
                system tray icon, or with "fcc stop".
  fcc status    Check whether it's currently running.
  fcc open      Just open the Admin UI in your browser.
  fcc stop      Convenience stop via taskkill (the tray icon's Quit is the
                primary way; this is here for scripting/dev-loop use).
  fcc help      Show this message.
`;

async function cmdStart() {
  if (process.platform !== "win32") {
    console.error(
      "fcc currently ships a Windows build only. On macOS/Linux, run the " +
        "project from source instead (see the repo README), or extend " +
        ".github/workflows/build-windows.yml to also build on " +
        "macos-latest/ubuntu-latest and add matching download logic here.",
    );
    process.exitCode = 1;
    return;
  }

  if (await isRunning(DEFAULT_HEALTH_URL)) {
    console.log("Already running.");
    console.log(`Admin UI: ${DEFAULT_ADMIN_URL}`);
    openInBrowser(DEFAULT_ADMIN_URL);
    return;
  }

  const exePath = await ensureDownloaded();
  console.log("Starting Free Claude Code in the background...");
  launchDetached(exePath);

  const ready = await waitUntilReady(DEFAULT_HEALTH_URL);
  if (ready) {
    console.log(`Ready: ${DEFAULT_ADMIN_URL}`);
    console.log("It will keep running after this terminal closes.");
    console.log('Look for its icon in the system tray - "Quit" stops it (or run "fcc stop").');
  } else {
    console.log(
      "Launched, but it did not report healthy within a few seconds.\n" +
        "Check the tray icon, or ~/.fcc/logs, for what's going on.",
    );
  }
}

async function cmdStatus() {
  const running = await isRunning(DEFAULT_HEALTH_URL);
  console.log(running ? `Running - ${DEFAULT_ADMIN_URL}` : "Not running.");
}

async function cmdOpen() {
  openInBrowser(DEFAULT_ADMIN_URL);
}

async function cmdStop() {
  if (process.platform !== "win32") {
    console.error("fcc stop is only implemented for Windows right now.");
    process.exitCode = 1;
    return;
  }
  const ok = await stopViaTaskkill();
  console.log(ok ? "Stopped." : "Nothing to stop (it wasn't running).");
}

async function main() {
  const arg = (process.argv[2] || "start").toLowerCase();
  switch (arg) {
    case "start":
      await cmdStart();
      break;
    case "status":
      await cmdStatus();
      break;
    case "open":
      await cmdOpen();
      break;
    case "stop":
      await cmdStop();
      break;
    case "help":
    case "--help":
    case "-h":
      console.log(HELP);
      break;
    default:
      console.error(`Unknown command: ${arg}\n${HELP}`);
      process.exitCode = 1;
  }
}

main().catch((err) => {
  console.error(err.message || err);
  process.exitCode = 1;
});
