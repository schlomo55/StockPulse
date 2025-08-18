from __future__ import annotations

from datetime import datetime
from typing import Final, TypedDict
import asyncio
import httpx

from app.core.FileLogger import FileLogger


class DailyOpenClose(TypedDict):
    status: str
    from_: str
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    afterHours: float
    preMarket: float


class PolygonStockDataProvider:
    """Polygon.io implementation for Daily Open/Close endpoint."""

    BASE_URL: Final[str] = "https://api.polygon.io/v1/open-close"

    def __init__(self, api_key: str, timeout_seconds: float, max_retries: int, logger: FileLogger) -> None:
        """Initialize the PolygonStockDataProvider with required configuration.
        
        Args:
            api_key: Polygon.io API key for authentication.
            timeout_seconds: HTTP request timeout duration in seconds.
            max_retries: Maximum number of retry attempts for failed requests.
            logger: FileLogger instance for logging operations and errors.
        """
        self._api_key = api_key
        self._max_retries = max_retries
        self._logger = logger
        self._timeout = httpx.Timeout(timeout_seconds)

    async def get_daily_open_close(self, symbol: str, date_yyyy_mm_dd: str) -> DailyOpenClose:
        """Fetch daily OHLC data from Polygon.io with retry logic.
        
        Args:
            symbol: Stock symbol to fetch data for (e.g., "AAPL", "GOOGL"). Will be converted to uppercase.
            date_yyyy_mm_dd: Date string in YYYY-MM-DD format for the trading data.
            
        Returns:
            DailyOpenClose: Dictionary containing OHLC data, volume, and market status information.
            
        Raises:
            ValueError: When stock symbol is not found or no data available for the date (404 response).
            RuntimeError: When API returns non-200/404 status codes or after all retry attempts fail.
        """
        symbol_upper = symbol.upper()
        url = f"{self.BASE_URL}/{symbol_upper}/{date_yyyy_mm_dd}"
        
        params = {"apiKey": self._api_key} if self._api_key else {}
        max_attempts = max(0, self._max_retries) + 1

        last_exception: Exception | None = None
        for attempt in range(max_attempts):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.get(url, params=params)
                date_object = datetime.strptime(date_yyyy_mm_dd, "%Y-%m-%d").date()
                if response.status_code == 404:
                    if date_object.weekday() > 4:
                        raise ValueError(f"No market on the Week-end")
                    raise ValueError(f"Symbol not found or no data for date: {symbol_upper} {date_yyyy_mm_dd}")
                if response.status_code != 200:
                    raise RuntimeError(f"Polygon error {response.status_code}: {response.text}")
                
                data = response.json()
                # Map to our TypedDict, renaming 'from' -> 'from_'
                result: DailyOpenClose = {
                    "status": data["status"],
                    "from_": data["from"],
                    "symbol": data["symbol"],
                    "open": float(data["open"]),
                    "high": float(data["high"]),
                    "low": float(data["low"]),
                    "close": float(data["close"]),
                    "volume": int(data["volume"]),
                    "afterHours": float(data.get("afterHours", 0.0)),
                    "preMarket": float(data.get("preMarket", 0.0)),
                }
                return result
            
            except ValueError:
                # Don't retry on 404
                self._logger.info(f"Polygon 404 for {symbol_upper} {date_yyyy_mm_dd}")
                raise
            except Exception as exc:
                last_exception = exc
                if attempt < max_attempts - 1:  # Not the last attempt
                    backoff_seconds = 0.2 * (2 ** attempt)
                    self._logger.debug(
                        f"Retrying Polygon request (attempt {attempt + 1}/{max_attempts - 1}) "
                        f"in {backoff_seconds:.1f}s: {exc}"
                    )
                    await asyncio.sleep(backoff_seconds)
                else:
                    self._logger.error("Polygon request failed after all retries", exc=exc)
                    if isinstance(exc, RuntimeError):
                        raise
                    raise RuntimeError(str(exc)) from exc

        # Should never reach here, but just in case
        raise RuntimeError(str(last_exception) if last_exception else "Unknown error")