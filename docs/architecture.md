# Architecture: Stocks REST API

This document describes the high-level architecture, module layout, responsibilities, and class relationships for the CIAL DnB Backend Assignment implementation.

## High-Level Overview

- Purpose: Provide a REST API to:
  - GET /stock/{symbol}: Aggregate OHLC data from Polygon.io and the MarketWatch "Performance" table; include stored `amount`. Supports optional `date` query parameter (YYYY-MM-DD format).
  - POST /stock/{symbol}: Update stock position with positive/negative amounts; returns final amount and market action (LONG/SHORT/NEUTRAL).
- Key principles: Separation of concerns, async/concurrency, testability via dependency injection, strong typing, and structured logging to files.

## Component Diagram (Textual)

- API Layer (FastAPI)
  - StockController
    - depends on StockService
- Service Layer
  - StockService
    - depends on PolygonStockDataProvider
    - depends on MarketWatchPerformanceScraper
    - depends on InMemoryStockRepository
    - depends on FileLogger
- Integrations
  - PolygonStockDataProvider (httpx)
  - MarketWatchPerformanceScraper (httpx + BeautifulSoup)
- Persistence
  - InMemoryStockRepository (dict-backed; thread-safe)
- Cross-cutting
  - FileLogger
- Models
  - Stock (Pydantic v2)
  - PurchaseRequest (Pydantic)

## Module Structure

- app/
  - api/
    - controllers/
      - StockController.py
  - services/
    - StockService.py
  - integrations/
    - PolygonStockDataProvider.py
    - MarketWatchPerformanceScraper.py
  - repositories/
    - InMemoryStockRepository.py
  - models/
    - Stock.py
    - PurchaseRequest.py
  - core/
    - FileLogger.py
- main.py (app factory wiring)
- tests/
  - test_file_logger.py
  - test_inmemory_stock_repository.py
  - test_polygon_stock_data_provider.py
  - test_marketwatch_performance_scraper.py
  - test_stock_service.py
  - test_stock_controller.py
  - test_main.py
  - __init__.py
- run_tests.py (unified test runner)
- pytest.ini (test configuration)
- logs/
  - .gitkeep (runtime logs written here)

## Responsibilities

- StockController
  - HTTP endpoints, schema validation, error mapping to HTTP status codes.
- StockService
  - Orchestrates data retrieval and scraping concurrently, merges with repository amount.
  - Tolerates scraping failures (returns performance = {}). Upstream provider failures bubble with proper mapping.
- PolygonStockDataProvider
  - Calls Polygon.io Daily Open/Close; adds retries, timeouts, API key handling; maps fields to internal types.
- MarketWatchPerformanceScraper
  - Scrapes MarketWatch “Performance” table; returns key/value dict; robust parsing with graceful fallback and logging.
- InMemoryStockRepository
  - Thread-safe in-memory storage of amounts per symbol; uppercase normalization for keys.
- Core
  - FileLogger: Two-file logging (general/error) with ISO-8601 timestamps; thread-safe appends.

## Interaction Flows

- GET /stock/{symbol}
  1) Controller validates symbol and optional date parameter (YYYY-MM-DD format). If date format is invalid, returns HTTP 400.
  2) Controller calls StockService.get_stock(symbol, date) where date is the provided parameter or the last trading day if not specified.
  3) Service runs provider and scraper concurrently.
  4) Provider result awaited first; if it fails, request fails (ValueError -> 404, RuntimeError -> 502).
  5) Scraper errors are tolerated: performance defaults to {} and error is logged.
  6) Amount loaded from repository (default 0).
  7) Stock model returned to controller and serialized as JSON.

- POST /stock/{symbol}
  1) Controller validates PurchaseRequest body (supports positive/negative integer amounts).
  2) Service updates repository and returns new total.
  3) Controller determines market action: LONG (final > 0), SHORT (final < 0), NEUTRAL (final = 0).
  4) Controller responds 201 with message, final_amount, and action.

## Key Classes (Signatures)

- app/models/Stock.py: Pydantic v2 BaseModel with alias for "from" field (stored as from_). Configured with populate_by_name.
- app/models/PurchaseRequest.py: Validates integer amount (positive to add, negative to subtract).
- app/integrations/PolygonStockDataProvider.py: Async httpx implementation with retries/backoff and API key; includes DailyOpenClose TypedDict.
- app/integrations/MarketWatchPerformanceScraper.py: Async httpx + BeautifulSoup parser implementation for performance data.
- app/repositories/InMemoryStockRepository.py: Thread-safe dict storage with RLock for amount tracking.
- app/services/StockService.py: Orchestrates concurrency and merging.
- app/api/controllers/StockController.py: FastAPI routes and error mapping.
- app/core/FileLogger.py: Writes logs/general.log and logs/error.log.

## Design Notes

- Simplified, non-over-engineered architecture using concrete classes directly.
- Standard Python exceptions (ValueError, RuntimeError) instead of custom exception classes.
- Inline date handling using date.today().isoformat() instead of separate utility modules.
- Configuration via .env file only, eliminating multiple configuration file options.
- Dependency injection supported via the create_app factory function for testing purposes.
- Concurrency with asyncio.gather/tasks in the service layer.
- Centralized logging with meaningful messages for long-running or error paths.
- Tolerant scraper failure policy to maintain core GET functionality.

## Non-functional Considerations

- Typing: All public methods include type hints.
- Docker: The application will be containerized and exposed on port 8000.
- Testing: Comprehensive test suite with 157 test cases covering all components including unit tests, integration tests, error handling, concurrency testing, and edge cases. Tests use dependency injection and mocking to avoid external dependencies.

## Future Enhancements

- Date fallback to last trading day when today has no data.
- Persistent repository (e.g., SQLite/Postgres) via a new IStockRepository implementation.
- Caching and rate-limiting for scraping.
- Structured logging (JSON) and rotation if necessary.
