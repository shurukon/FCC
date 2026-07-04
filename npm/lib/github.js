"use strict";

const pkg = require("../package.json");

// !!! UPDATE THESE to your own fork/repo before publishing this package !!!
// This npm package only ever downloads from wherever windows-build.yml
// actually published its GitHub Release - that has to be *your* repo, since
// upstream Alishahryar1/free-claude-code doesn't have the tray app,
// multi-key pooling, or Kilo Gateway support this build includes.
const REPO_OWNER = "shurukon";
const REPO_NAME = "FCC";

const ASSET_NAME = "FreeClaudeCode-windows.zip";

function releaseTag(version) {
  return `v${version || pkg.version}`;
}

function releaseAssetUrl(version) {
  const tag = releaseTag(version);
  return `https://github.com/${REPO_OWNER}/${REPO_NAME}/releases/download/${tag}/${ASSET_NAME}`;
}

function releasePageUrl(version) {
  return `https://github.com/${REPO_OWNER}/${REPO_NAME}/releases/tag/${releaseTag(version)}`;
}

module.exports = { REPO_OWNER, REPO_NAME, ASSET_NAME, releaseTag, releaseAssetUrl, releasePageUrl };
