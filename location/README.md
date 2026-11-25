# Location MCP (`location`)

Geolocation and geocoding MCP server (`Location-Server`) exposing SSE on container port `8080` (host port `8087` via `docker-compose.yml`).

Combines multi-provider GeoIP (`ipwho.is`, `ip-api.com`, `ipapi.co`, `freeipapi.com`) with Open-Meteo Geocoding and OpenStreetMap Nominatim.

## Tools

### `get_current_location(ip_address: str = "") -> str`
Resolve geographic location (city, region, country, postal code, coordinates, timezone, public IP, ISP) for the current host or a given public IPv4/IPv6 address.

- **Parameters**:
  - `ip_address` (`str`, optional, default `""`): Public IPv4/IPv6 address. Empty string, private/loopback/reserved IPs, or aliases (`"auto"`, `"self"`, `"me"`, `"current"`, `"my"`, `"localhost"`) trigger auto-detection (or return `DEFAULT_LOCATION_*` env overrides if configured).

### `reverse_geocode(latitude: float, longitude: float) -> str`
Convert decimal coordinates into a street address, neighborhood, city/town, state/region, postal code, and country via OpenStreetMap Nominatim.

- **Parameters**:
  - `latitude` (`float`, required): Latitude in `[-90, 90]`.
  - `longitude` (`float`, required): Longitude in `[-180, 180]`.

### `search_location(query: str, count: int = 5) -> str`
Search for a city, town, street address, or landmark by name and return matching coordinates (plus timezone and elevation when available).

- **Parameters**:
  - `query` (`str`, required): Place name, city, landmark, or street address.
  - `count` (`int`, optional, default `5`): Maximum matches to return, clamped to `[1, 10]`.
- **Behavior**: Queries Open-Meteo Geocoding first and falls back to OpenStreetMap Nominatim for street addresses and landmarks.

## Environment Variables (Optional)
Used when auto-detecting current location:
- `DEFAULT_LOCATION_CITY` (enables static override when set)
- `DEFAULT_LOCATION_REGION`, `DEFAULT_LOCATION_COUNTRY`, `DEFAULT_LOCATION_COUNTRY_CODE`, `DEFAULT_LOCATION_POSTAL`
- `DEFAULT_LOCATION_LAT`, `DEFAULT_LOCATION_LON`, `DEFAULT_LOCATION_TIMEZONE`, `DEFAULT_LOCATION_IP`

## How to Run

### Docker Compose (Recommended)
From the repository root:
```bash
docker compose up -d --build location
```
SSE endpoint: `http://localhost:8087/sse`

### Standalone Docker
```bash
docker build -t walpaca-mcp-location ./location
docker run -d --name walpaca_mcp_location -p 8087:8080 walpaca-mcp-location
```

### Local Python
```bash
cd location
pip install httpx "mcp<2"
python server.py
```
SSE endpoint: `http://localhost:8080/sse`

## Configure in Other Tools

### Generic MCP Client (SSE)
- **Transport**: `sse`
- **URL**: `http://localhost:8087/sse`

### JSON Client Config (Cursor / Windsurf / MCP-compatible clients)
```json
{
  "mcpServers": {
    "location": {
      "url": "http://localhost:8087/sse"
    }
  }
}
```

### Claude Desktop (via `mcp-remote` SSE bridge)
```json
{
  "mcpServers": {
    "location": {
      "command": "npx",
      "args": ["mcp-remote", "http://localhost:8087/sse"]
    }
  }
}
```

## Usage Examples
- Detect the user's current city and timezone (`get_current_location`) before calling `get_current_weather`.
- Convert GPS coordinates from a photo or log into a street address via `reverse_geocode`.
- Disambiguate cities with identical names (e.g., `"Springfield"`) via `search_location`.
