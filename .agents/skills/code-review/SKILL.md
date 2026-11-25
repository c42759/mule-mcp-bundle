---
name: code-review
description: Review git diff changes since a fixed point (commit, branch, tag, or merge-base) along two parallel axes—Standards and Spec—using isolated sub-agents. Use when the user wants to review a branch, PR, work-in-progress changes, or asks to "review since X".
allowed-tools: read_file run_command invoke_subagent
metadata:
  version: 1.0.0
  author: c42759
---

# Code Review

## Overview & Scope

Performs a two-axis review of the diff between `HEAD` and a user-supplied fixed point:

- **Standards**: Does the code conform to this repo's documented coding standards and baseline code-smell heuristics?
- **Spec**: Does the code faithfully implement the originating issue or specification?

Both axes run in **parallel sub-agents** with fresh context windows so findings do not pollute each other. A change can pass one axis and fail the other (e.g., clean code that implements the wrong spec, or spec-accurate code that breaks repo conventions); reporting them separately prevents one axis from masking the other.

If the issue tracker integration is missing, instruct the user to run `/setup-matt-pocock-skills`.

## Step-by-Step Workflow

1. **Pin the Fixed Point.**
   - Resolve the user-supplied ref (commit SHA, branch name, tag, `main`, `HEAD~5`, etc.). If omitted, ask the user before proceeding.
   - Verify the ref resolves with `git rev-parse <fixed-point>` and confirm `git diff <fixed-point>...HEAD` (three-dot merge-base comparison) is non-empty. Capture `git log <fixed-point>..HEAD --oneline`. Fail fast here on bad refs or empty diffs rather than inside sub-agents.
2. **Identify the Spec Source.**
   Search in priority order:
   1. Issue references in commit messages (`#123`, `Closes #45`, GitLab `!67`, etc.), fetched via the tracker workflow.
   2. A spec path passed as an argument by the user.
   3. A spec file under `docs/`, `specs/`, or `.scratch/` matching the branch name or feature.
   4. If none found, ask the user where the spec is; if none exists, skip the Spec sub-agent and report "no spec available".
3. **Identify the Standards Sources & Smell Baseline.**
   - Locate all repo files documenting coding standards (`CODING_STANDARDS.md`, `CONTRIBUTING.md`, etc. must be included if present).
   - Always include the 12 Fowler code smells (_Refactoring_, ch. 3) as a baseline:
     - **Mysterious Name**: Function, variable, or type whose name hides its purpose -> rename it; if no honest name fits, design is murky.
     - **Duplicated Code**: Same logic shape appears in multiple hunks/files -> extract shared shape and call from both.
     - **Feature Envy**: Method reaches into another object's data more than its own -> move method onto the envied data.
     - **Data Clumps**: Same fields or params travel together repeatedly -> bundle into one type.
     - **Primitive Obsession**: Primitive/string standing in for a domain concept -> give the concept its own small type.
     - **Repeated Switches**: Same `switch`/`if`-cascade on the same type recurs -> replace with polymorphism or shared map.
     - **Shotgun Surgery**: One logical change forces scattered edits across many files -> gather into one module.
     - **Divergent Change**: One file/module edited for unrelated reasons -> split so each module changes for one reason.
     - **Speculative Generality**: Abstractions, params, or hooks added for unrequested future needs -> delete and inline until needed.
     - **Message Chains**: Long `a.b().c().d()` navigation -> hide walk behind one method on the first object.
     - **Middle Man**: Class/function mostly delegating onward -> cut it and call real target directly.
     - **Refused Bequest**: Subclass/implementer ignores or overrides most inherited behavior -> drop inheritance, use composition.
4. **Spawn Parallel Sub-Agents.**
   Launch both sub-agents concurrently in the foreground with fresh contexts:
   - **Standards Sub-Agent Brief**: Pass the diff command, commit list, discovered standards-source files, and the full 12-item smell baseline pasted inline. Instruct it to report per file/hunk: (a) documented standard violations citing file + rule (hard violations), and (b) baseline smells naming the smell and quoting the hunk (judgement calls). Skip anything tooling already enforces. Keep under 400 words.
   - **Spec Sub-Agent Brief**: Pass the diff command, commit list, and spec path or contents. Instruct it to report: (a) missing/partial requirements, (b) unrequested behavior (scope creep), and (c) implemented requirements that look wrong. Quote the spec line for each finding. Keep under 400 words.
5. **Aggregate Reports.**
   Present both reports side by side under `## Standards` and `## Spec` headings verbatim or lightly cleaned, followed by a one-line summary per axis.

## Rules & Guardrails

- **Always** validate the fixed point and non-empty diff before spawning sub-agents.
- **Always** paste the full smell baseline into the Standards sub-agent prompt (it has no external access to it).
- **Always** keep Standards and Spec findings strictly separated; repo-documented standards always override the smell baseline.
- **Never** merge, deduplicate, or rerank findings across the two axes, and never pick a single cross-axis winner.
- **Never** flag issues already enforced by repo linters, formatters, or type-checkers.
- **If/Then Logic:** If no spec exists after checking commits, args, and `docs/`/`specs/`/`.scratch/` and asking the user, then skip the Spec sub-agent and note "no spec available" under `## Spec`.

## Output Format

- `## Standards`: Sub-agent report (hard violations vs. judgement-call smells, < 400 words).
- `## Spec`: Sub-agent report or "no spec available" (< 400 words).
- **Summary**: One-line total findings per axis and the worst issue within each axis (if any).

## Examples

**Input:**

> Review my changes since `main` against `specs/auth-login.md`.

**Expected Output:**

> ## Standards
>
> - **Hard Violation (`CODING_STANDARDS.md` §3.1):** `src/auth/login.ts:42` uses `any` on token payload.
> - **Judgement Call (Primitive Obsession):** `src/auth/login.ts:18-24` passes raw `email: string` and `tenantId: string` separately across 4 helpers.
>
> ## Spec
>
> - **Missing (`specs/auth-login.md` L14):** "Lock account after 5 failed attempts" is not implemented.
> - **Scope Creep:** `src/auth/login.ts:70` adds password-reset email trigger not requested in spec.
>
> **Summary:** Standards: 2 findings (worst: `any` token payload); Spec: 2 findings (worst: missing 5-attempt lockout).
