#!/usr/bin/env pwsh
# Warbell release publisher — the mechanical half of the `/release` skill.
#
# Single repo now: the game code, the website (site/), and the GitHub release all live in
# `miskibin/warbell`. (The old `warbell-game` website repo was merged in; its Pages site is
# served from site/ here and the download links resolve to THIS repo's releases.)
#
# The skill (Claude) does the JUDGMENT half BEFORE calling this:
#   * bump `version` in Cargo.toml and commit it (this script pushes it),
#   * write player-facing release notes to a markdown file (passed via -NotesFile),
#   * write the changelog.html entry under site/ and commit/push it.
#
# This script does the deterministic half:
#   1. read the version from Cargo.toml  -> tag vX.Y.Z
#   2. cargo build --release             (build.rs embeds the version into the exe)
#   3. wix build warbell.wxs             -> Warbell-Setup.msi
#        (version auto-binds from the exe; STABLE filename so the website's
#         releases/latest/download/Warbell-Setup.msi link never changes)
#   4. push main + push the tag          -> release.yml CI builds the canonical GitHub
#                                            release (zip + per-version signed MSI)
#   5. publish/refresh the release with our handwritten notes + Warbell-Setup.msi attached
#        (the stable-name asset the website download resolves to). Create-or-update, so it
#        is robust whether the script or CI gets to the tag's release first.
#
# Usage:  pwsh scripts/release.ps1 -NotesFile dist-notes.md
param(
    [Parameter(Mandatory)] [string] $NotesFile,
    [string] $SiteRepo = "miskibin/warbell"
)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)   # repo root

if (-not (Test-Path $NotesFile)) { throw "notes file not found: $NotesFile" }

$verLine = Select-String -Path Cargo.toml -Pattern '^version\s*=\s*"([^"]+)"' | Select-Object -First 1
if (-not $verLine) { throw "could not read version from Cargo.toml" }
$ver = $verLine.Matches[0].Groups[1].Value
$tag = "v$ver"
Write-Host "==> Releasing Warbell $tag" -ForegroundColor Cyan

# 1+2. Build the release exe (embeds $ver via build.rs).
Write-Host "==> cargo build --release"
cargo build --release
if ($LASTEXITCODE) { throw "cargo build failed ($LASTEXITCODE)" }

# 3. Build the website installer (stable name; version bound to the exe's FileVersion).
Write-Host "==> wix build -> Warbell-Setup.msi"
wix build warbell.wxs -arch x64 -ext WixToolset.UI.wixext -o Warbell-Setup.msi
if ($LASTEXITCODE) { throw "wix build failed ($LASTEXITCODE)" }

# 4. Push main + the tag -> the main-repo CI builds the canonical GitHub release.
Write-Host "==> push main + tag $tag"
git push origin main
git tag $tag
git push origin $tag

# 5. Publish/refresh the release with our handwritten notes + the stable-name MSI.
#    Same repo as CI now, so the script and release.yml race for the tag's release. The script
#    normally wins (CI's matrix build takes ~30-45 min); CI's softprops/action-gh-release later
#    ADDS the zips + per-version signed MSI to this same release and leaves our notes intact.
#    If CI (or a re-run) created the release first, update it instead of failing.
Write-Host "==> publish release $tag on $SiteRepo (notes + Warbell-Setup.msi)"
gh release view $tag --repo $SiteRepo --json tagName 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "    release exists -> updating notes + (re)uploading MSI"
    gh release edit   $tag --repo $SiteRepo --notes-file $NotesFile
    gh release upload $tag --repo $SiteRepo --clobber "Warbell-Setup.msi"
} else {
    Write-Host "    creating release"
    gh release create $tag --repo $SiteRepo --title "Warbell $tag" --notes-file $NotesFile "Warbell-Setup.msi"
}

Write-Host "==> Done." -ForegroundColor Green
Write-Host "    CI (release.yml) is building the canonical zips + signed MSI for $tag."
Write-Host "    Installer published as Warbell-Setup.msi (stable download link)."
