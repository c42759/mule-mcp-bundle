---
name: unslop
description: Prose Humanizer and AI De-Slopper that audits and removes formulaic AI writing patterns, empty corporate buzzwords, and robotic cadence while preserving all facts. Use when checking text for AI tells, humanizing drafts, or running a quality gate on writer output.
allowed-tools: read_file write_file edit_file
metadata:
  version: 1.0.0
  author: c42759
---

# Unslop

## Overview & Scope

Audits and humanizes prose by eliminating artificial intelligence tells, robotic cadence, hollow abstractions, and formulaic framing. Operates in two modes:

1. **Audit Mode** (`audit` / "check AI tells"): Diagnoses concrete defects without altering original prose.
2. **Rewrite Mode** (`rewrite` / "humanize" / "de-slop"): Two-pass reconstruction preserving all facts, constraints, technical specs, user opinions, and quantities.

Also serves as a quality gate for writers (e.g., Mark) and any agent generating human-facing copy.

## Step-by-Step Workflow

1. **Analyze Input & Select Mode.**
   - Determine whether the user requested Audit Mode or Rewrite Mode (default to auditing first before changing clean human prose).
   - **Pass 1 (Diagnose & Extract)**: Catalog all core factual claims, data points, constraints, domain-valid technical terms, explicit quotes, and author intent. Flag defects against the AI Tell Catalog:
     - _Scaffolding & Transitional Clichés_: "Here's the thing:", "Let that sink in", "At the end of the day", "In today's fast-paced world / digital landscape", "It's important to remember", "Whether you're an X or a Y", "When it comes to X", "Look no further", "Delve into", "Tapestry", "Beacon", "Testament to", "Game-changer", "Revolutionize", "Elevate", "Supercharge".
     - _Hollow Evaluation & Unearned Praise_: Vague buzzwords lacking mechanism or metric ("seamless integration", "cutting-edge solution", "streamlined experience")—either specify _how_/_what_ changes or delete the adjective.
     - _Robotic Symmetry & Structural Tells_: Uniform sentence lengths, parallel list templates in every section, forced three-part lists ("fast, reliable, and secure"), inanimate agency ("This library empowers developers to..." -> "Developers use this library to..."), faux-profound summary conclusions ("In conclusion, the future of X is bright").
     - _Empty Filler_: Introductory windup sentences removable without losing core information.
2. **Execute Core Task.**
   - In **Audit Mode**: Produce a concise diagnostic report quoting exact defective spans, naming the AI tell, explaining the defect, and recommending a plain replacement. Leave original prose untouched.
   - In **Rewrite Mode (Pass 2 - Reconstruct)**: Rebuild prose using plain diction, varied sentence length, and natural human rhythm while retaining every cataloged fact and constraint.
3. **Verify Output.**
   - Cross-check that zero facts, quantities, or technical specifications were dropped or invented.
   - Present proposed text/file diffs for explicit user approval before modifying files.

## Rules & Guardrails

- **Always** audit first and leave clean, human prose untouched.
- **Always** preserve all factual claims, technical specifications, user opinions, explicit quotes, and specific quantities.
- **Always** prefer plain diction and direct agent/action phrasing over inflated rhetoric or tool personification.
- **Always** present proposed text/code changes for user review before applying edits.
- **Never** invent metrics, benefits, or claims to replace deleted fluff.
- **If/Then Logic:** If running as a quality gate over another writer's draft, then reject marketing fluff and formulaic structure while respecting domain-valid technical terms and deliberate stylistic choices.

## Output Format

- **Audit Mode**: Bullet list of `[Quoted Span]` -> `[AI Tell Category]` -> `[Contextual Defect & Plain Replacement]`.
- **Rewrite Mode**: Clean reconstructed prose (or diff/artifact if editing a file) plus a brief summary of removed tells.

## Examples

**Input:**

> Audit: "In today's fast-paced digital landscape, this game-changing library empowers developers to delve into seamless, fast, reliable, and secure workflows."

**Expected Output:**

> - `"In today's fast-paced digital landscape"` -> **Scaffolding Cliché / Empty Filler**: Delete windup.
> - `"game-changing"` -> **Hollow Evaluation**: Remove unearned praise or state specific capability.
> - `"empowers developers to delve into"` -> **Inanimate Agency + Cliché**: Replace with `"Developers use this library to..."`.
> - `"seamless, fast, reliable, and secure"` -> **Hollow Buzzwords + Forced List**: Specify actual mechanism/metrics or cut.
