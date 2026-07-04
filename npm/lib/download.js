"use strict";

const fs = require("fs");
const https = require("https");
const path = require("path");
const { execFileSync } = require("child_process");

const { releaseAssetUrl, releasePageUrl } = require("./github");
const { cacheRoot, versionDir, appDir, exePath, downloadTmpZipPath } = require("./paths");

const MAX_REDIRECTS = 5;

function httpsGetFollowingRedirects(url, redirectsLeft, onResponse) {
  https
    .get(url, { headers: { "User-Agent": "free-claude-code-npm" } }, (res) => {
      const { statusCode, headers } = res;
      if (statusCode >= 300 && statusCode < 400 && headers.location) {
        res.resume(); // discard this response body
        if (redirectsLeft <= 0) {
          onResponse(new Error(`Too many redirects fetching ${url}`), null);
          return;
        }
        httpsGetFollowingRedirects(headers.location, redirectsLeft - 1, onResponse);
        return;
      }
      if (statusCode !== 200) {
        res.resume();
        onResponse(new Error(`Download failed: HTTP ${statusCode} for ${url}`), null);
        return;
      }
      onResponse(null, res);
    })
    .on("error", (err) => onResponse(err, null));
}

function downloadFile(url, destPath) {
  return new Promise((resolve, reject) => {
    fs.mkdirSync(path.dirname(destPath), { recursive: true });
    const tmpPath = `${destPath}.part`;
    httpsGetFollowingRedirects(url, MAX_REDIRECTS, (err, res) => {
      if (err) {
        reject(err);
        return;
      }
      const fileStream = fs.createWriteStream(tmpPath);
      res.pipe(fileStream);
      fileStream.on("finish", () => {
        fileStream.close((closeErr) => {
          if (closeErr) {
            reject(closeErr);
            return;
          }
          fs.renameSync(tmpPath, destPath);
          resolve();
        });
      });
      fileStream.on("error", reject);
      res.on("error", reject);
    });
  });
}

function extractZip(zipPath, destDir) {
  fs.mkdirSync(destDir, { recursive: true });
  // Expand-Archive ships with Windows PowerShell / PowerShell 7 - no extra
  // npm dependency needed just to unzip one file.
  execFileSync(
    "powershell.exe",
    [
      "-NoProfile",
      "-NonInteractive",
      "-Command",
      `Expand-Archive -LiteralPath '${zipPath}' -DestinationPath '${destDir}' -Force`,
    ],
    { stdio: "inherit" },
  );
}

/**
 * Ensure the given (or current package) version's build is downloaded and
 * extracted, returning the path to the .exe. Downloads are cached per
 * version under paths.cacheRoot() - a version that's already present is
 * reused as-is without re-checking the network.
 */
async function ensureDownloaded(version) {
  const exe = exePath(version);
  if (fs.existsSync(exe)) {
    return exe;
  }

  const url = releaseAssetUrl(version);
  const zipPath = downloadTmpZipPath(version);
  console.log(`Downloading Free Claude Code (first run only) from:\n  ${url}`);
  try {
    await downloadFile(url, zipPath);
  } catch (err) {
    throw new Error(
      `${err.message}\n\n` +
        `Could not download the build. Make sure a GitHub Release exists at:\n` +
        `  ${releasePageUrl(version)}\n` +
        `(built by .github/workflows/build-windows.yml on a "v${version}" tag push).`,
    );
  }

  console.log("Extracting...");
  extractZip(zipPath, versionDir(version));
  fs.rmSync(zipPath, { force: true });

  if (!fs.existsSync(exe)) {
    throw new Error(
      `Extraction finished but ${exe} is missing - the release asset's ` +
        `internal folder layout may not match what paths.js expects.`,
    );
  }
  return exe;
}

module.exports = { ensureDownloaded, cacheRoot, appDir, exePath };
