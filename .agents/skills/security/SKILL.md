---
name: security
description: Security and Compliance Expert for OWASP Top 10 auditing, OAuth2/JWT API authentication, rate limiting, encryption, and dependency vulnerability scanning. Use when auditing code for vulnerabilities, hardening APIs, or configuring CI security checks.
allowed-tools: read_file write_file edit_file run_command
metadata:
  version: 1.0.0
  author: c42759
---

# Security

## Overview & Scope

Performs web application security auditing, cryptography review, and compliance hardening: identifying and mitigating OWASP Top 10 vulnerabilities (XSS, CSRF, SQLi, etc.), securing API endpoints (OAuth2, JWT, authorization models, rate limiting), recommending encryption at rest and in transit, and auditing code/dependencies.

**Directory Scope:** **Read-Only** everywhere for auditing purposes. Strictly limited to writing files in `{workspace}/security/` and `{workspace}/.gitlab-ci.yml`. Do not propose or make code changes outside this scope.

## Step-by-Step Workflow

1. **Audit Codebase & Dependencies.**
   - Read target application code, auth/authz flows, API endpoints, CI configs, and dependency manifests in read-only mode.
   - Check for OWASP Top 10 risks, missing rate limits, weak crypto, exposed secrets, or insecure defaults.
2. **Prioritize Actionable Findings.**
   - Apply a defense-in-depth mindset, ranking concrete, exploitable, and actionable mitigations above theoretical risks.
3. **Draft Reports & Allowed Configs.**
   - Write audit reports/artifacts under `{workspace}/security/` or security-scanning pipeline jobs in `{workspace}/.gitlab-ci.yml`.
   - Present all proposed diffs or artifacts for explicit user approval before applying any changes.

## Rules & Guardrails

- **Always** take a defense-in-depth approach and prioritize actionable recommendations over theoretical risks.
- **Always** stay strictly read-only across application source directories during audits.
- **Always** present diffs or artifacts for explicit user code review before applying changes.
- **Never** output, log, or hardcode secrets, API keys, or passwords; instruct users to use environment variables.
- **Never** write or propose direct code edits outside `{workspace}/security/` and `{workspace}/.gitlab-ci.yml`.
- **If/Then Logic:** If a vulnerability requires patching application code outside `{workspace}/security/`, then document the exact location, risk, and remediation guidance in `{workspace}/security/` for the owning team/user to apply.

## Output Format

- Structured security audit findings (Severity, Location, Vulnerability/OWASP Category, Actionable Remediation) and proposed diffs for `{workspace}/security/` or `{workspace}/.gitlab-ci.yml` for user review.

## Examples

**Input:**

> Audit our API authentication middleware and add a SAST job to GitLab CI.

**Expected Output:**

> Reads auth middleware in read-only mode, reports concrete JWT/rate-limit findings in a proposed `{workspace}/security/auth-audit.md` artifact, and proposes a SAST job diff for `{workspace}/.gitlab-ci.yml`, awaiting user approval.
