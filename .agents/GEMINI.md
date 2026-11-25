# Global Workspace Rules

- **Code Review Required**: Agents will never be able to make code changes without the developer (USER) code reviewing the changes. Always present the proposed code changes (e.g., using artifacts or diffs) and request explicit approval from the USER before directly applying them to the codebase, unless specifically instructed otherwise by the user in the moment.

- **Command Execution Restrictions**: Agents are strictly prohibited from running destructive commands (e.g., `rm`, `git reset --hard`, `git push --force`), installing new dependencies (`pip install`, `dnf`/`apt` installs), or mutating running containers/services (`docker compose up/down/restart`, `systemctl`) without prior, explicit user approval.

- **Workspace Sandboxing**: Agents must restrict all file modifications and command execution strictly to the current project workspace. Modifying files outside of this workspace (like `~/.ssh`, `~/.gnupg`, `~/.aws`, `~/.kube`, `~/.docker/config.json`, or host system paths) is strictly forbidden without explicit approval.

- **Network Isolation**: Agents must not initiate network requests to external servers (e.g., using `curl`, `wget`, or custom scripts) to send data out of the system. Localhost SSE/HTTP checks against `127.0.0.1:8081`–`8088` are permitted when verifying live MCP server containers; external network requests are only allowed for fetching documentation or when explicitly directed by the user. Automated tests must mock external HTTP/API calls (DuckDuckGo, Open-Meteo, Nominatim, GeoIP providers, YouTube/noembed).

- **Secret Handling**: Agents must never output, log, or transmit hardcoded secrets, API keys, or passwords. Configuration overrides use container environment variables in `docker-compose.yml`; never expose `.env` files, private keys, or credential stores (see `SEARCH_EXCLUDE_GLOBS` in `linux-utils/server.py`).

- **Mandatory Planning Phase**: Before executing any code changes or taking action on a request, you MUST ALWAYS generate an implementation plan artifact for the user to review and approve. Your plan MUST strictly contain the following sections:
  1. **Description of the request**: A summary of what is being asked.
  2. **Possible use cases**: The real-world use cases or scenarios for the requested change.
  3. **Active Agents**: Which specialized roles or subagents (e.g., `mcp-servers`, `docker`, `security`, `testing`, `research`, `documentation`, `release`) will be required to accomplish the changes.
  4. **Agent Goals**: The specific goal and domain focus of each active agent in the plan.
  5. **Task Assignment**: A concrete list of tasks to be completed, clearly indicating which agent is assigned to which task (and parallel vs sequential execution).

- **Caveman Communication Mode (DEFAULT)**: All agents MUST use ultra-compressed "caveman" style communication to save tokens.
  - **Rules**: Drop articles (a/an/the), conversational filler (just/basically/really), pleasantries (sure/certainly), and hedging. Sentence fragments are OK. Use short synonyms.
  - **Strict Boundaries**: Do NOT narrate tool calls. Do NOT use decorative tables/emojis.
  - **Technical Accuracy**: ALWAYS keep technical terms, API names, code blocks, exact CLI commands, and raw error strings verbatim. Do not compress code.
  - **Persistence**: This mode is ACTIVE EVERY RESPONSE by default. Never self-reference the mode (e.g. no "caveman mode on").
  - **Toggling**: If the user types `/nocaveman`, immediately disable this mode and revert to normal, verbose professional communication. If the user types `/caveman`, immediately re-enable this compressed mode.

- **Subagents & Parallel Execution**: Delegate to subagents when tasks benefit from specialized roles, isolated context, independent validation, or concurrent execution.
  - **When to Delegate**: Use subagents for broad multi-area research, independent module work, or dedicated verification. Keep trivial single-file lookups or tight sequential edits in the main agent.
  - **Testing & Validation Subagents**: Use subagents for test authoring, running test suites/linters/builds, and independently validating implementation against user requirements and edge cases to prevent regressions and missed gaps.
  - **Parallel Dispatch**: Launch independent, non-overlapping subtasks concurrently in the same turn (e.g., parallel read-only research across separate components, disjoint implementation tracks, or concurrent test/validation runs).
  - **Write Isolation**: Never run concurrent write subagents against overlapping files in the same workspace. Assign strictly disjoint file paths or use isolated workspaces (`share` / `branch`).
  - **Rule Inheritance**: Every subagent MUST obey all Global Workspace Rules (`Code Review Required`, `Command Execution Restrictions`, `Workspace Sandboxing`, `Network Isolation`, `Secret Handling`, `Caveman Communication Mode`) and `.agents-memory` protocols. Include key constraints and file ownership in each subagent prompt.
  - **Coordinator Gate**: Subagents may research, validate, draft diffs, or propose changes, but the main agent must synthesize proposals and obtain explicit USER approval before applying codebase edits (unless user explicitly waived review).
  - **No Polling**: Do not poll subagents in loops; wait for reactive completion messages.
  - **Plan Alignment**: In the **Mandatory Planning Phase**, mark parallel vs sequential tasks under `Task Assignment` and list each active subagent role (including test/validation roles) under `Active Agents` and `Agent Goals`.

# Project Rules & Rules of Engagement

All agents must strictly follow the localized Memory Bank protocols below.

## 1. The Memory Bank Protocol
- **Before Starting User Request:**
  - **Directory Check:** If `.agents-memory` does not exist at project root, create it immediately.
  - **File Bootstrap & Analysis:** Check for required memory files: `project-brief.md`, `system-patterns.md`, `tech-context.md`, `active-context.md`, `progress.md`. If any are missing, create them, thoroughly analyze project codebase/structure, and populate each file with accurate, relevant project data before proceeding with user request.
- **On Initialization:** You must immediately read all files inside `.agents-memory/` (`project-brief.md`, `system-patterns.md`, `tech-context.md`, `active-context.md`, `progress.md`) to align your mental model with the current project state.
- **During the Session:** Update `active-context.md` whenever core engineering focuses or task priorities shift.
- **On Wrap-up:** Before concluding any long sequence of tasks, update `progress.md` and any relevant contextual files to log what was accomplished and outline next steps for the next session.

## 2. Technical & Architectural Rules
- Look at `.agents-memory/tech-context.md` to check approved packages, Python runtime, and tech stacks before adding anything.
- Adhere strictly to the styles and architecture patterns logged in `.agents-memory/system-patterns.md`:
  - **All 8 MCP Services** (`fetch`, `web-search`, `youtube`, `website`, `memory`, `weather`, `location`, `linux-utils`): Python `3.11-slim` containers running `"mcp<2"` (`FastMCP(..., host="0.0.0.0", port=8080)` with `transport="sse"`), exposed via `docker-compose.yml` on host ports `8081`–`8088`. `@mcp.tool()` handlers must return `str` and catch exceptions gracefully; docstrings must use fake placeholder examples.
  - `website/`: Enforce `validate_public_url` SSRF protections and `is_allowed_by_robots` `robots.txt` checks.
  - `memory/`: Enforce `sanitize_folder_uuid` path containment inside `MEMORY_BASE_DIR`, `_FILE_LOCK` concurrency protection, atomic `save_knowledge_graph` writes, `trash.json` archiving, and read-only `default` inheritance inside folder scopes.
  - `linux-utils/`: Keep all host volume mounts `:ro`; run `subprocess.run` with `shell=False`, timeouts, and `MAX_OUTPUT_CHARS` truncation; preserve `_validate_unit`, `_resolve_safe_path`, and `SEARCH_EXCLUDE_GLOBS`.
  - `location/`: Preserve `normalize_target_ip` private/loopback filtering and multi-provider GeoIP fallback.
- **Verification**:
  - Python unit tests: `python3 -m unittest discover -s linux-utils -p "test_*.py"`
  - Python syntax check: `python3 -m py_compile` on modified `.py` files.
  - Compose validation: `docker compose config` (when modifying `docker-compose.yml` or `Dockerfile`s).
- **Project Skills**: Prefer project-relevant skills in `.agents/skills/` (`architecture`, `code-review`, `documentation`, `release`, `security`, `testing`, `unslop`); `backend` (Django/DRF) and `database` are unused template skills for this stack.
