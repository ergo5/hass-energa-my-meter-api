---
description: HACS default repository submission and PR management rules
---

# HACS Submission Rules

## PR Management — CRITICAL

1. **NEVER create a new PR if an existing one was closed by a reviewer.** Instead:
   - Fix the issue in your repository
   - Comment on the CLOSED PR asking the reviewer to reopen
   - Only create a new PR if the reviewer explicitly says to
   - **Reason**: New PR = end of queue (FIFO). Reopen preserves position.

2. **NEVER create a PR without verifying the required format first.** Check:
   - All 6 checklist boxes must be checked (`- [x]`)
   - 3 links required for integrations: Current Release, HACS Action, Hassfest Action
   - Title format: `Adds new integration [owner/repo]`

3. **Queue position is based on PR creation date (FIFO).** New PR = end of queue.

## Merge Conflict Prevention — CRITICAL

The `integration` file in `hacs/default` changes frequently. Merge conflicts are the #1 cause of PR failures.

1. **NEVER merge `master` into your feature branch** — this risks losing your added line during conflict resolution.
2. **Always create a fresh branch from current `hacs/default:master`** — this avoids conflicts entirely:
   ```bash
   gh repo sync ergo5/default --branch master
   git fetch origin master
   git checkout -b add-energa-mobile-vN origin/master
   ```
3. **Verify the diff before pushing**: `git diff master` must show exactly **1 added line**.
4. **After submission, do NOT touch the branch** unless the reviewer explicitly asks.

## Before Submitting

1. Run HACS validation locally or verify GitHub Actions pass
2. Verify `hacs.json` contains ONLY allowed keys: `name`, `render_readme`, `country`
   - **Do NOT include**: `domain`, `codeowners`, `documentation`, `requirements`, `version`, `config_flow`
3. Verify `manifest.json` version matches latest release tag
4. Verify latest release tag exists and is clean

## After PR is Open

Bot rules (strictly follow):
- **Do NOT comment** unless withdrawing or sharing critical info
- **Do NOT open another PR** — it creates duplicate work
- **Do NOT ask others to comment**
- **Do NOT merge default branch** unless reviewer asks

## Review Process

- Queue: ~94 PRs as of Feb 19, 2026, review speed ~3-5/day
- Wait time: 2-3 weeks typical
- If reviewer requests changes → PR goes to draft → fix → mark ready → back in queue

## Past Failures Reference

| PR | Failure | Root Cause |
|---|---|---|
| #5413 | Bot reject | Submitted from `master` branch |
| #5414 | Bot reject | Missing checklist/links |
| #5415 | Bot reject | Incomplete checklist |
| #5416 | Reviewer close | Extra keys in `hacs.json` |
| #5537 | Reviewer close | Merge conflict wiped the added line → 0 changes |
