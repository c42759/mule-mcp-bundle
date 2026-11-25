# Linux Utils MCP (`linux-utils`)

Read-only Linux host inspection MCP server (`Linux-Utils-Server`) exposing SSE on container port `8080` (host port `8088` via `docker-compose.yml`).

Runs `fastfetch`, `lsblk`, `sensors`, `systemctl`, `journalctl`, and `ripgrep` (`rg`) without a shell (`shell=False`), with timeouts and `15,000`-character output truncation. All host mounts in `docker-compose.yml` are read-only (`:ro`).

## Tools

### `get_hardware_info() -> str`
Retrieve structured host hardware, OS, kernel, CPU, GPU, and memory info via `fastfetch --format json`.

### `get_storage_info() -> str`
List host block devices, partitions, filesystems, labels, sizes, usage percentages, available space, and mount points via `lsblk -J --fs -o NAME,SIZE,TYPE,FSTYPE,LABEL,FSUSE%,FSAVAIL,MOUNTPOINTS`.

### `get_sensors() -> str`
Read live host hardware temperatures, voltages, and fan speeds via `sensors -j` (`lm-sensors`).

### `check_systemd_services(unit: str = "") -> str`
Check host systemd service status.

- **Parameters**:
  - `unit` (`str`, optional, default `""`): Systemd unit name (`^[a-zA-Z0-9@_.:\-]+$`, e.g., `"nginx.service"`). Leave empty to list all failed units (`systemctl list-units --failed --no-pager`).

### `get_service_logs(unit: str, lines: int = 50) -> str`
Fetch recent host `journalctl` log lines for a systemd unit.

- **Parameters**:
  - `unit` (`str`, required): Validated systemd unit name.
  - `lines` (`int`, optional, default `50`): Number of recent lines, clamped to `[1, 200]`.

### `search_files(pattern: str, directory: str = "") -> str`
Search host file contents using `ripgrep` inside `SEARCH_ROOTS` (default `/host/home`).

- **Parameters**:
  - `pattern` (`str`, required): Regex or literal text to search.
  - `directory` (`str`, optional, default `""`): Subdirectory inside an allowed root. Defaults to the first configured `SEARCH_ROOTS` entry.
- **Security & Limits**: Respects `.gitignore`, skips binary files and files > 2 MB, caps at 10 matches per file (`15,000` chars total), and excludes `.ssh/**`, `.gnupg/**`, `.password-store/**`, `.aws/**`, `.kube/**`, `.docker/config.json`, `.env*`, `*.pem`, `*.key`, `id_rsa*`, and `id_ed25519*`.

## Environment Variables
- `SEARCH_ROOTS`: Colon-separated allowed search roots (default `/host/home`).
- `LINUX_UTILS_SEARCH_DIR`: Host path mounted to `/host/home:ro` in `docker-compose.yml` (default `${HOME}`).
- `SYSTEMD_IGNORE_CHROOT`: Set to `"1"` in `docker-compose.yml` so `systemctl`/`journalctl` work inside the container against mounted host sockets/logs.

## How to Run

### Docker Compose (Recommended)
From the repository root:
```bash
docker compose up -d --build linux-utils
```
SSE endpoint: `http://localhost:8088/sse`

### Local Python
Requires `fastfetch`, `rg` (`ripgrep`), `lm-sensors`, `systemctl`, `journalctl`, and `lsblk` installed on the host:
```bash
cd linux-utils
pip install -r requirements.txt
SEARCH_ROOTS="$HOME" python server.py
```
SSE endpoint: `http://localhost:8080/sse`

### Unit Tests
```bash
python3 -m unittest discover -s linux-utils -p "test_*.py"
```

## Configure in Other Tools

### Generic MCP Client (SSE)
- **Transport**: `sse`
- **URL**: `http://localhost:8088/sse`

### JSON Client Config (Cursor / Windsurf / MCP-compatible clients)
```json
{
  "mcpServers": {
    "linux-utils": {
      "url": "http://localhost:8088/sse"
    }
  }
}
```

### Claude Desktop (via `mcp-remote` SSE bridge)
```json
{
  "mcpServers": {
    "linux-utils": {
      "command": "npx",
      "args": ["mcp-remote", "http://localhost:8088/sse"]
    }
  }
}
```

## Usage Examples
- Check host CPU/GPU/RAM specs (`get_hardware_info`) or disk usage (`get_storage_info`).
- Spot failing systemd services (`check_systemd_services()`) and inspect their logs (`get_service_logs("nginx.service", lines=100)`).
- Monitor CPU/GPU temperatures (`get_sensors`) or search local project files (`search_files("TODO", "/host/home/projects")`).
