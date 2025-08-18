# How It Works (Plain Language)

This project is a small web service that lets you:
- Look up a stock by its ticker (like AAPL) and get a combined view of:
  - Official market data (open, high, low, close, volume, pre-market, after-hours) for today from Polygon.io
  - A “Performance” snapshot scraped from the MarketWatch stock page
  - Your currently recorded amount (how many units you’ve added so far)
- Update your stock position by adding (positive amounts) or subtracting (negative amounts) units, with automatic LONG/SHORT position determination.

## Endpoints

- GET /stock/{symbol}
  - Optional query parameter: `date` (in YYYY-MM-DD format)
  - Examples: 
    - GET /stock/AAPL (uses the last trading day)
    - GET /stock/AAPL?date=2024-01-15 (uses specific date)
  - The service asks Polygon.io for the specified date's data (or the last trading day if no date provided) and scrapes MarketWatch for the performance table at the same time (in parallel).
  - It then combines those results with your stored amount (defaults to 0) and returns everything as a single JSON object.

- POST /stock/{symbol}
  - Example bodies: { "amount": 5 } to add units or { "amount": -10 } to subtract units
  - Updates your position and returns the final amount plus market action (LONG/SHORT/NEUTRAL)
  - LONG = final amount > 0, SHORT = final amount < 0, NEUTRAL = final amount = 0

## Where the data comes from

- Polygon.io (official market data):
  - The API endpoint is /v1/open-close/{symbol}/{YYYY-MM-DD}
  - The project expects the API key in the POLYGON_API_KEY environment variable.
- MarketWatch (performance data):
  - The service downloads the HTML page https://www.marketwatch.com/investing/stock/{symbol} and extracts the "Performance" table into a dictionary.
  - If the page structure changes and the table can’t be found, the service still returns the response with an empty performance object and logs the parsing failure.

## What is stored

- Your “amount” entries are stored in memory (inside the running process). This means they reset when the server restarts. This satisfies the assignment requirement without introducing a database. A persistent storage can be added later if desired.

## Concurrency

- The GET /stock/{symbol} endpoint performs two tasks in parallel:
  - Requesting Polygon data
  - Scraping MarketWatch
- This makes the endpoint faster than doing them one after another.

## Logging

- The service writes log messages to files under the logs/ folder:
  - logs/general.log — informational and debug messages
  - logs/error.log — errors and stack traces
- All log entries include an ISO-8601 timestamp and log level.

## Configuration

- Preferred: create a `.env` or `config.env` file in the project root with the following keys:
  - POLYGON_API_KEY=your_polygon_api_key_here
  - HTTP_TIMEOUT_SECONDS=10.0
  - HTTP_MAX_RETRIES=2
- The application will automatically load the first file it finds (.env preferred) at startup.
- Fallback: environment variables with the same names are still supported and will override file values if set.

## Error handling behavior

- If an invalid date format is provided (not YYYY-MM-DD), the API responds with HTTP 400 (Bad Request).
- If the Polygon request returns 404 (symbol not found or no data for the specified date), the API responds with HTTP 404.
- If Polygon fails (timeouts, 5xx), the API responds with HTTP 502 (Bad Gateway).
- If MarketWatch scraping fails, the API still responds with HTTP 200 but sets performance to {} and logs the error.

## Example responses

- POST /stock/AAPL with { "amount": 5 } -> 201
  {
    "message": "5 units of stock AAPL were added to your stock record",
    "final_amount": 15,
    "action": "LONG"
  }

- POST /stock/AAPL with { "amount": -20 } -> 201
  {
    "message": "20 units of stock AAPL were subtracted from your stock record", 
    "final_amount": -5,
    "action": "SHORT"
  }

- GET /stock/AAPL -> 200
  {
    "afterHours": 129.85,
    "close": 130.15,
    "from": "2025-08-16",
    "high": 133.41,
    "low": 129.89,
    "open": 130.465,
    "preMarket": 129.6,
    "status": "OK",
    "symbol": "AAPL",
    "volume": 70790813,
    "performance": { 
  -   "5 Day": "0.98%",
      "1 Month": "9.66%",
      "3 Month": "9.62%",
      "YTD": "-7.52%",
      "1 Year": "2.45%"},
    "amount": 5
  }
