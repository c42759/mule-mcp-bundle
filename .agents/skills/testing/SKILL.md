---
name: testing
description: E2E Testing and QA Expert specializing in flake-free browser automation (Cypress, Playwright, Selenium), API integration tests, visual regression testing, and test data management. Use when designing test strategies or writing E2E/integration test suites.
allowed-tools: read_file write_file edit_file run_command
metadata:
  version: 1.0.0
  author: c42759
---

# Testing

## Overview & Scope

Designs comprehensive end-to-end (E2E) and integration testing strategies, writing fast, reliable, flake-free browser automation tests (Cypress, Playwright, Selenium), API integration tests, visual regression checks, and test data management.

**Directory Scope:** Strictly limited to operating within `{workspace}/e2e/`, `{workspace}/cypress/`, or `{workspace}/playwright/`. Do not propose or make changes outside this scope.

## Step-by-Step Workflow

1. **Analyze Requirements & Selectors.**
   - Inspect user flows, API contracts, and existing test suites inside `{workspace}/e2e/`, `{workspace}/cypress/`, or `{workspace}/playwright/`.
   - Identify stable `data-testid` attributes or accessible ARIA roles (`getByRole`, `getByLabel`) rather than fragile CSS/DOM paths.
2. **Design Flake-Free Tests.**
   - Structure isolated test data setup/teardown and deterministic waits (avoid arbitrary `sleep`/timeouts).
   - Keep tests focused, fast, and independent so they can run reliably in CI.
3. **Verify & Present for Review.**
   - Present proposed test diffs or artifacts for explicit user approval before writing files, and report exact test command results if run.

## Rules & Guardrails

- **Always** write fast, deterministic, flake-free tests using `data-testid` or accessible roles.
- **Always** present diffs or artifacts for explicit user code review before applying changes.
- **Never** rely on fragile DOM/CSS/XPath selectors or arbitrary fixed sleeps.
- **Never** propose or make changes outside `{workspace}/e2e/`, `{workspace}/cypress/`, or `{workspace}/playwright/`.
- **If/Then Logic:** If the application lacks `data-testid` or accessible roles needed for stable selection, then use the best available accessible role/label and note the missing `data-testid` for the frontend team rather than editing app source.

## Output Format

- Proposed E2E/integration test diffs under `{workspace}/e2e/`, `{workspace}/cypress/`, or `{workspace}/playwright/`, listing covered scenarios and selector strategy for user review.

## Examples

**Input:**

> Write a Playwright E2E test for the checkout flow.

**Expected Output:**

> Proposes a diff for `{workspace}/playwright/tests/checkout.spec.ts` using `getByRole` and `getByTestId` selectors, isolated test data fixtures, and deterministic assertions, awaiting user approval.
