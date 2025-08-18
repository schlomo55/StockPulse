from __future__ import annotations
import os
from pathlib import Path
from typing import Optional, Any
from fastapi import FastAPI
from dotenv import load_dotenv

from app.api.controllers.StockController import StockController, router as stock_router
from app.services.StockService import StockService
from app.repositories.InMemoryStockRepository import InMemoryStockRepository
from app.core.FileLogger import FileLogger


def _load_config() -> tuple[str, float, int]:
    """Load configuration from environment variables with defaults.
    
    Returns:
        tuple[str, float, int]: A tuple containing:
            - api_key (str): Polygon.io API key from POLYGON_API_KEY env var, empty string if not set
            - timeout_seconds (float): HTTP timeout from HTTP_TIMEOUT_SECONDS env var, defaults to 10.0
            - max_retries (int): Max retry attempts from HTTP_MAX_RETRIES env var, defaults to 2
            
    Raises:
        ValueError: If environment variables contain invalid numeric values.
    """
    try:
        load_dotenv()
    except Exception:
        # If .env loading fails, continue with system environment variables
        pass
    
    api_key = os.environ.get("POLYGON_API_KEY", "")
    
    try:
        timeout_seconds = float(os.environ.get("HTTP_TIMEOUT_SECONDS", "10.0"))
        if timeout_seconds <= 0:
            raise ValueError("HTTP_TIMEOUT_SECONDS must be positive")
    except ValueError as e:
        raise ValueError(f"Invalid HTTP_TIMEOUT_SECONDS value: {e}") from e
    
    try:
        max_retries = int(os.environ.get("HTTP_MAX_RETRIES", "2"))
        if max_retries < 0:
            raise ValueError("HTTP_MAX_RETRIES must be non-negative")
    except ValueError as e:
        raise ValueError(f"Invalid HTTP_MAX_RETRIES value: {e}") from e
    
    return api_key, timeout_seconds, max_retries


def create_app(
    *,
    logger: Optional[FileLogger] = None,
    repository: Optional[InMemoryStockRepository] = None,
    provider: Optional[Any] = None,
    scraper: Optional[Any] = None,
) -> FastAPI:
    """Create and configure the FastAPI application with dependency injection support.
    
    Args:
        logger: Optional FileLogger instance. If None, creates a new FileLogger with default settings.
        repository: Optional InMemoryStockRepository instance. If None, creates a new empty repository.
        provider: Optional stock data provider instance. If None, creates PolygonStockDataProvider with config.
        scraper: Optional performance scraper instance. If None, creates MarketWatchPerformanceScraper.
        
    Returns:
        FastAPI: Configured FastAPI application instance with all routes and dependencies wired up.
    """
    app = FastAPI(title="Stocks API", version="1.0.0")
    
    # Initialize dependencies
    file_logger = logger or FileLogger(Path("logs"))
    stock_repository = repository or InMemoryStockRepository()

    # Configure provider
    if provider is None:
        from app.integrations.PolygonStockDataProvider import PolygonStockDataProvider
        api_key, timeout_seconds, max_retries = _load_config()
        stock_provider = PolygonStockDataProvider(api_key, timeout_seconds, max_retries, file_logger)
    else:
        stock_provider = provider

    # Configure scraper
    if scraper is None:
        from app.integrations.MarketWatchPerformanceScraper import MarketWatchPerformanceScraper
        performance_scraper = MarketWatchPerformanceScraper(file_logger)
    else:
        performance_scraper = scraper

    # Wire up services and controllers
    service = StockService(stock_provider, performance_scraper, stock_repository, file_logger)
    controller = StockController(service)
    controller.register(stock_router)
    app.include_router(stock_router)

    @app.get("/")
    async def root():
        """Root endpoint that returns a simple status message.
        
        Returns:
            dict[str, str]: Dictionary containing a status message indicating the API is running.
        """
        return {"message": "Stocks API is running"}

    return app


# Create app instance for production use
app = create_app()
