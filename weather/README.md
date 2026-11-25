# Weather MCP (`weather`)

Open-Meteo weather MCP server (`Weather-Server`) exposing SSE on container port `8080` (host port `8086` via `docker-compose.yml`).

Geocodes city/town names via `geocoding-api.open-meteo.com` and retrieves live conditions or 1–7 day forecasts from `api.open-meteo.com` with WMO weather code descriptions.

## Tools

### `get_current_weather(location: str, temperature_unit: str = "celsius") -> str`
Get live current weather conditions for any city, town, or location.

- **Parameters**:
  - `location` (`str`, required): City, town, or place name (e.g., `"Lisbon"`, `"New York"`).
  - `temperature_unit` (`str`, optional, default `"celsius"`): `"celsius"` (`°C`, `km/h`, `mm`) or `"fahrenheit"` (`°F`, `mph`, `inch`).
- **Behavior**: Returns resolved place name, coordinates, condition, temperature, feels-like temperature, humidity, precipitation, and wind speed.

### `get_weather_forecast(location: str, days: int = 3, temperature_unit: str = "celsius") -> str`
Get a daily multi-day weather forecast (1 to 7 days) for any city, town, or location.

- **Parameters**:
  - `location` (`str`, required): City, town, or place name.
  - `days` (`int`, optional, default `3`): Number of forecast days, clamped to `[1, 7]`.
  - `temperature_unit` (`str`, optional, default `"celsius"`): `"celsius"` or `"fahrenheit"`.
- **Behavior**: Returns daily condition, min/max temperatures, total precipitation, and max precipitation probability (`%`).

## How to Run

### Docker Compose (Recommended)
From the repository root:
```bash
docker compose up -d --build weather
```
SSE endpoint: `http://localhost:8086/sse`

### Standalone Docker
```bash
docker build -t walpaca-mcp-weather ./weather
docker run -d --name walpaca_mcp_weather -p 8086:8080 walpaca-mcp-weather
```

### Local Python
```bash
cd weather
pip install httpx "mcp<2"
python server.py
```
SSE endpoint: `http://localhost:8080/sse`

## Configure in Other Tools

### Generic MCP Client (SSE)
- **Transport**: `sse`
- **URL**: `http://localhost:8086/sse`

### JSON Client Config (Cursor / Windsurf / MCP-compatible clients)
```json
{
  "mcpServers": {
    "weather": {
      "url": "http://localhost:8086/sse"
    }
  }
}
```

### Claude Desktop (via `mcp-remote` SSE bridge)
```json
{
  "mcpServers": {
    "weather": {
      "command": "npx",
      "args": ["mcp-remote", "http://localhost:8086/sse"]
    }
  }
}
```

## Usage Examples
- Check current temperature and wind conditions before commuting.
- Chain `location` (`get_current_location`) -> `weather` (`get_current_weather`) when the user asks "what's the weather here?".
- Plan travel or outdoor events with a 5- or 7-day `get_weather_forecast`.
