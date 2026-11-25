# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.0] - 2026-11-25

### Changed

- Improved `@mcp.tool()` docstrings across all 8 MCP servers (`fetch`, `web-search`, `website`, `linux-utils`, `weather`, `youtube`, `location`, `memory`) with clearer LLM usage instructions, parameter constraints, clamping/truncation limits, and tool-chaining guidance.
- Replaced real personal/company data in tool docstring examples with fake placeholder examples.

## [1.0.0] - 2026-11-22

### Added

- Initial repository setup (`README.md`, `.gitignore`) and `docker-compose.yml` orchestrating 8 containerized FastMCP SSE servers:
  - **fetch**: `fetch_web_page` for raw HTTP GET retrieval.
  - **web-search**: `search_ddg` (DuckDuckGo) and `fetch_web_page`.
  - **website**: `scrape_website` and `extract_website_links` with SSRF protection and `robots.txt` checking.
  - **youtube**: `get_youtube_transcript` and `query_youtube_transcript`.
  - **memory**: `store_fact`, `recall_facts`, and `delete_fact` backed by a folder-scoped JSON knowledge graph with `trash.json` archiving.
  - **weather**: `get_current_weather` and `get_weather_forecast` powered by Open-Meteo.
  - **location**: `get_current_location`, `reverse_geocode`, and `search_location` with multi-provider GeoIP fallback and OpenStreetMap Nominatim.
  - **linux-utils**: `get_hardware_info`, `get_storage_info`, `get_sensors`, `check_systemd_services`, `get_service_logs`, and `search_files` with read-only root scoping and secret-file exclusions, plus unit tests in `linux-utils/test_server.py`.
