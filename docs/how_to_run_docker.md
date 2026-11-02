# How to Run with Docker

This guide shows how to build and run the Stocks API in Docker without passing parameters at run time. The app now reads configuration from a config file (.env or config.env) automatically.

Prerequisites
- Docker Desktop (or Docker Engine)
- A config file with your Polygon.io API key (see below)

Create a Config File
1) In the project root, create your `.env` from the template: `cp .env.example .env` (`.env` is git-ignored, so it is not part of the repository). Then set your key. The file should look like:
```
POLYGON_API_KEY=your_polygon_api_key_here
HTTP_TIMEOUT_SECONDS=10.0
HTTP_MAX_RETRIES=2
```

Build the Image
1) Open a terminal in the project root (the folder with the Dockerfile).
2) Build the image:
   docker build -t stocks-api:latest .

Run the Container (no -e needed)
Option A: Mount the .env file at runtime (recommended)
- Windows PowerShell:
  docker run --rm -p 8000:8000 -v "${PWD}\.env:/app/.env" stocks-api:latest
- Linux/macOS:
  docker run --rm -p 8000:8000 -v "$(pwd)/.env:/app/.env" stocks-api:latest

Option B: Bake a config.env into the image (not recommended for secrets)
- Create a file named `config.env` in the project root with the same KEY=VALUE pairs.
- Because the Dockerfile uses `COPY . .`, the file will be included during build. Then simply run:
  docker run --rm -p 8000:8000 stocks-api:latest

Check the API
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Sample requests:
  - GET a stock (replace AAPL with your symbol):
    curl http://localhost:8000/stock/AAPL
  - POST amount:
    curl -X POST http://localhost:8000/stock/AAPL -H "Content-Type: application/json" -d "{\"amount\": 5}"

Optional: Map Logs to Host
To persist logs on the host machine, mount the logs directory:
- Windows PowerShell (from the project root):
  docker run --rm -p 8000:8000 -v "${PWD}\.env:/app/.env" -v "${PWD}\logs:/app/logs" stocks-api:latest
- Linux/macOS:
  docker run --rm -p 8000:8000 -v "$(pwd)/.env:/app/.env" -v "$(pwd)/logs:/app/logs" stocks-api:latest

Alternate Run (env variables fallback)
You can still pass environment variables directly if you prefer:
- Windows PowerShell:
  docker run --rm -p 8000:8000 -e POLYGON_API_KEY="<your_api_key>" stocks-api:latest
- Linux/macOS:
  docker run --rm -p 8000:8000 -e POLYGON_API_KEY=<your_api_key> stocks-api:latest

Alternate Port
If port 8000 is busy on your machine:
- docker run --rm -p 8080:8000 -v "${PWD}\.env:/app/.env" stocks-api:latest
Then open http://localhost:8080/docs

Stopping the Container
- If started in the foreground, press Ctrl+C.
- If started in the background (add -d), stop by name or ID:
  docker ps
  docker stop <container_id>

Troubleshooting
- HTTP 401/403 from Polygon: Ensure POLYGON_API_KEY is set correctly in your .env/config.env.
- Network/timeout errors: Increase HTTP_TIMEOUT_SECONDS and/or HTTP_MAX_RETRIES in your config file.
- Empty performance data: The MarketWatch page structure can change; the API still responds with performance = {} and logs a warning.
- Proxy/Corporate network: Configure Docker/HTTP proxies as required by your environment.

Notes
- Base image uses Python 3.12-slim.
- The in-memory amount store resets when the container restarts. Use a persistent repository if you need durability.
