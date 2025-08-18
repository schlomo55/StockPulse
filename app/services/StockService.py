from __future__ import annotations
import asyncio

from app.integrations.PolygonStockDataProvider import PolygonStockDataProvider, DailyOpenClose
from app.integrations.MarketWatchPerformanceScraper import MarketWatchPerformanceScraper
from app.repositories.InMemoryStockRepository import InMemoryStockRepository
from app.models.Stock import Stock
from app.core.FileLogger import FileLogger


class StockService:
    """Coordinates data retrieval, scraping, and repository updates."""

    def __init__(
        self,
        provider: PolygonStockDataProvider,
        scraper: MarketWatchPerformanceScraper,
        repository: InMemoryStockRepository,
        logger: FileLogger,
    ) -> None:
        """Initialize the StockService with required dependencies.
        
        Args:
            provider: PolygonStockDataProvider instance for fetching OHLC data from Polygon.io.
            scraper: MarketWatchPerformanceScraper instance for scraping performance data.
            repository: InMemoryStockRepository instance for managing stock amounts.
            logger: FileLogger instance for logging operations and errors.
        """
        self._provider = provider
        self._scraper = scraper
        self._repository = repository
        self._logger = logger

    async def get_stock(self, symbol: str, date_yyyy_mm_dd: str) -> Stock:
        """Fetch Polygon and MarketWatch data concurrently, merge with amount, return Stock.

        Args:
            symbol: Stock symbol to fetch data for (e.g., "AAPL", "GOOGL").
            date_yyyy_mm_dd: Date string in YYYY-MM-DD format for the trading data.
            
        Returns:
            Stock: Complete stock data model containing OHLC data, performance metrics, and amount.
            
        Raises:
            ValueError: When stock symbol is not found or no data available for the date (404 from Polygon).
            RuntimeError: When upstream API failures occur (non-404 errors from Polygon).
            
        Note:
            Scraping failures are tolerated: performance is set to {} and a log entry is created.
            Provider failures propagate (404 -> ValueError, others -> RuntimeError).
        """
        # Run concurrently but handle scraper failure gracefully
        provider_task = asyncio.create_task(self._provider.get_daily_open_close(symbol, date_yyyy_mm_dd))
        scraper_task = asyncio.create_task(self._scraper.get_performance(symbol))

        # Await provider first; if it fails, raise immediately
        try:
            polygon_data: DailyOpenClose = await provider_task
        except Exception:
            # Ensure scraper task is cancelled if provider fails
            scraper_task.cancel()
            raise

        performance_data: dict[str, str]
        try:
            performance_data = await scraper_task
            # Handle None values from scraper by converting to empty dict
            if performance_data is None:
                performance_data = {}
        except Exception as exc:
            # Tolerate scraper errors
            self._logger.error("Performance scraping failed; returning empty performance", exc=exc)
            performance_data = {}

        amount = self._repository.get_amount(symbol)
        return Stock(
            afterHours=polygon_data["afterHours"],
            close=polygon_data["close"],
            from_=polygon_data["from_"],
            high=polygon_data["high"],
            low=polygon_data["low"],
            open=polygon_data["open"],
            preMarket=polygon_data["preMarket"],
            status=polygon_data["status"],
            symbol=polygon_data["symbol"],
            volume=polygon_data["volume"],
            performance=performance_data,
            amount=amount,
        )

    def add_amount(self, symbol: str, amount: int) -> int:
        """Increase stored amount for a stock symbol and return the new total.
        
        Args:
            symbol: Stock symbol to add amount to (e.g., "AAPL", "GOOGL").
            amount: Integer amount to add to the existing total.
            
        Returns:
            int: The new total amount after addition.
        """
        return self._repository.add_amount(symbol, amount)