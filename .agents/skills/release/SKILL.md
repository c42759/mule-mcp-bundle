---
name: release
description: >-
  Guides creating a new semantic-versioned release for Bytey AI Companion:
  collects commits since the last git tag, updates CHANGELOG.md and the GNOME
  extension metadata.json version-name, commits both files, creates a matching
  vX.Y.Z git tag, and prompts before pushing. Use when the user asks to make,
  prepare, cut, or tag a new release.
---

# Release Workflow

Follow this procedure when cutting a new release. Respect all workspace rules
(`Mandatory Planning Phase`, `Code Review Required` before editing files).

## Steps

### 1. Gather Changes Since Last Tag
1. Find latest tag and inspect commits since that tag:
   ```bash
   LAST_TAG=$(git describe --tags --abbrev=0)
   git log --oneline "${LAST_TAG}..HEAD"
   git log --stat "${LAST_TAG}..HEAD"
   ```
2. Read `CHANGELOG.md` (check existing `## [Unreleased]` entries) and
   `gnome-extension/bytey-ai-companion@c42759.github.com/metadata.json`
   (check current `"version-name"`).
3. Determine next SemVer `X.Y.Z` from the changes since `LAST_TAG`:
   - **MAJOR (`X+1.0.0`)**: Breaking changes, incompatible config/IPC/CLI shifts.
   - **MINOR (`X.Y+1.0`)**: New user-facing features, providers, tools, or UI additions.
   - **PATCH (`X.Y.Z+1`)**: Bug fixes, hardening, docs, or internal refactors only.
   - If the bump level is ambiguous, confirm `X.Y.Z` with the user before editing.

### 2. Update `CHANGELOG.md`
1. Follow [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/).
2. Move/merge `## [Unreleased]` items and all notable commits from
   `${LAST_TAG}..HEAD` into `## [<version>] - <YYYY-MM-DD>` grouped under
   `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`.
3. Keep an empty `## [Unreleased]` header above `## [<version>]`.
4. Update footer comparison links:
   ```markdown
   [Unreleased]: https://github.com/c42759/bytey-ai-companion/compare/v<version>...HEAD
   [<version>]: https://github.com/c42759/bytey-ai-companion/compare/<LAST_TAG>...v<version>
   ```

### 3. Update Extension `metadata.json`
1. Edit `gnome-extension/bytey-ai-companion@c42759.github.com/metadata.json`.
2. Update `"version-name"` to `"<version>"` (without `v` prefix), matching the
   version added to `CHANGELOG.md`.
3. Validate JSON syntax:
   ```bash
   python3 -m json.tool gnome-extension/bytey-ai-companion@c42759.github.com/metadata.json > /dev/null
   ```

### 4. Review, Commit, and Tag
1. Present `CHANGELOG.md` and `metadata.json` diffs to the user for approval
   (unless already approved in the current turn).
2. Stage and commit both files together:
   ```bash
   git add CHANGELOG.md gnome-extension/bytey-ai-companion@c42759.github.com/metadata.json
   git commit -m "chore(release): v<version>"
   ```
3. Create the matching git tag:
   ```bash
   git tag "v<version>"
   ```
4. Verify commit, tag, and clean tree:
   ```bash
   git log -n 1 --decorate --oneline && git tag -l "v<version>" && git status --short
   ```

### 5. Prompt Before Pushing
- Never run `git push` automatically.
- Ask the user explicitly whether to push the branch commit and tag:
  `git push && git push origin "v<version>"`
- Only push after explicit user confirmation.
