"use strict";

const pkg = require("../package.json");

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
