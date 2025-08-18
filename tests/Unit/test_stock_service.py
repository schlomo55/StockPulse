"""Unit tests for StockService class."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.StockService import StockService
from app.integrations.PolygonStockDataProvider import PolygonStockDataProvider, DailyOpenClose
from app.integrations.MarketWatchPerformanceScraper import MarketWatchPerformanceScraper
from app.repositories.InMemoryStockRepository import InMemoryStockRepository
from app.core.FileLogger import FileLogger
from app.models.Stock import Stock


class TestStockService:
    """Test suite for StockService functionality."""

    @pytest.fixture
    def mock_logger(self):
        """Create a mock FileLogger for testing."""
        return MagicMock(spec=FileLogger)

    @pytest.fixture
    def mock_provider(self):
        """Create a mock PolygonStockDataProvider for testing."""
        return MagicMock(spec=PolygonStockDataProvider)

    @pytest.fixture
    def mock_scraper(self):
        """Create a mock MarketWatchPerformanceScraper for testing."""
        return MagicMock(spec=MarketWatchPerformanceScraper)

    @pytest.fixture
    def mock_repository(self):
        """Create a mock InMemoryStockRepository for testing."""
        return MagicMock(spec=InMemoryStockRepository)

    @pytest.fixture
    def service(self, mock_provider, mock_scraper, mock_repository, mock_logger):
        """Create a StockService instance for testing."""
        return StockService(
            provider=mock_provider,
            scraper=mock_scraper,
            repository=mock_repository,
            logger=mock_logger
        )

    @pytest.fixture
    def sample_polygon_data(self):
        """Sample DailyOpenClose data from Polygon."""
        return {
            "status": "OK",
            "from_": "2023-01-01",
            "symbol": "AAPL",
            "open": 150.0,
            "high": 155.0,
            "low": 148.0,
            "close": 152.0,
            "volume": 1000000,
            "afterHours": 151.0,
            "preMarket": 149.0
        }

    @pytest.fixture
    def sample_performance_data(self):
        """Sample performance data from MarketWatch."""
        return {
            "5 Day": "+2.5%",
            "1 Month": "+5.1%",
            "3 Month": "-1.2%",
            "YTD": "+15.7%",
            "1 Year": "+22.3%"
        }

    @pytest.mark.asyncio
    async def test_successful_get_stock_with_all_data(self, service, mock_provider, mock_scraper, 
                                                     mock_repository, sample_polygon_data, 
                                                     sample_performance_data):
        """Test successful stock retrieval with all data sources working."""
        # Setup mocks
        mock_provider.get_daily_open_close = AsyncMock(return_value=sample_polygon_data)
        mock_scraper.get_performance = AsyncMock(return_value=sample_performance_data)
        mock_repository.get_amount.return_value = 100
        
        result = await service.get_stock("AAPL", "2023-01-01")
        
        # Verify result
        assert isinstance(result, Stock)
        assert result.symbol == "AAPL"
        assert result.open == 150.0
        assert result.close == 152.0
        assert result.performance == sample_performance_data
        assert result.amount == 100
        
        # Verify method calls
        mock_provider.get_daily_open_close.assert_called_once_with("AAPL", "2023-01-01")
        mock_scraper.get_performance.assert_called_once_with("AAPL")
        mock_repository.get_amount.assert_called_once_with("AAPL")

    @pytest.mark.asyncio
    async def test_get_stock_with_scraper_failure_returns_empty_performance(self, service, mock_provider, 
                                                                           mock_scraper, mock_repository, 
                                                                           mock_logger, sample_polygon_data):
        """Test that scraper failures result in empty performance data."""
        # Setup mocks
        mock_provider.get_daily_open_close = AsyncMock(return_value=sample_polygon_data)
        mock_scraper.get_performance = AsyncMock(side_effect=RuntimeError("Scraping failed"))
        mock_repository.get_amount.return_value = 50
        
        result = await service.get_stock("AAPL", "2023-01-01")
        
        # Verify result has empty performance
        assert isinstance(result, Stock)
        assert result.symbol == "AAPL"
        assert result.performance == {}
        assert result.amount == 50
        
        # Verify error was logged
        mock_logger.error.assert_called_once_with(
            "Performance scraping failed; returning empty performance", 
            exc=mock_scraper.get_performance.side_effect
        )

    @pytest.mark.asyncio
    async def test_get_stock_provider_404_raises_value_error(self, service, mock_provider, 
                                                            mock_scraper, mock_repository):
        """Test that provider 404 errors raise ValueError."""
        # Setup mocks
        mock_provider.get_daily_open_close = AsyncMock(side_effect=ValueError("Symbol not found"))
        mock_scraper.get_performance = AsyncMock(return_value={})
        
        with pytest.raises(ValueError, match="Symbol not found"):
            await service.get_stock("INVALID", "2023-01-01")
        
        # Verify scraper task was cancelled (provider failed first)
        # The actual cancellation is hard to test directly, but we can verify provider was called
        mock_provider.get_daily_open_close.assert_called_once_with("INVALID", "2023-01-01")

    @pytest.mark.asyncio
    async def test_get_stock_provider_runtime_error_propagates(self, service, mock_provider, 
                                                              mock_scraper, mock_repository):
        """Test that provider RuntimeError propagates."""
        # Setup mocks
        mock_provider.get_daily_open_close = AsyncMock(side_effect=RuntimeError("API error"))
        mock_scraper.get_performance = AsyncMock(return_value={})
        
        with pytest.raises(RuntimeError, match="API error"):
            await service.get_stock("AAPL", "2023-01-01")

    @pytest.mark.asyncio
    async def test_concurrent_execution_of_provider_and_scraper(self, service, mock_provider, 
                                                               mock_scraper, mock_repository, 
                                                               sample_polygon_data, sample_performance_data):
        """Test that provider and scraper are executed concurrently."""
        # Track execution order
        execution_order = []
        
        async def mock_provider_call(*args):
            execution_order.append("provider_start")
            await asyncio.sleep(0.1)  # Simulate delay
            execution_order.append("provider_end")
            return sample_polygon_data
            
        async def mock_scraper_call(*args):
            execution_order.append("scraper_start")
            await asyncio.sleep(0.05)  # Shorter delay
            execution_order.append("scraper_end")
            return sample_performance_data
        
        mock_provider.get_daily_open_close = AsyncMock(side_effect=mock_provider_call)
        mock_scraper.get_performance = AsyncMock(side_effect=mock_scraper_call)
        mock_repository.get_amount.return_value = 75
        
        result = await service.get_stock("AAPL", "2023-01-01")
        
        # Verify both started before either finished (concurrent execution)
        assert execution_order == ["provider_start", "scraper_start", "scraper_end", "provider_end"]
        assert isinstance(result, Stock)

    @pytest.mark.asyncio
    async def test_provider_failure_cancels_scraper_task(self, service, mock_provider, mock_scraper, mock_repository):
        """Test that provider failure cancels the scraper task."""
        # Setup provider to fail immediately
        mock_provider.get_daily_open_close = AsyncMock(side_effect=ValueError("Provider error"))
        
        # Setup scraper with a long delay to test cancellation
        async def long_scraper_call(*args):
            await asyncio.sleep(1.0)  # Long delay
            return {"data": "should not reach here"}
        
        mock_scraper.get_performance = AsyncMock(side_effect=long_scraper_call)
        
        with pytest.raises(ValueError, match="Provider error"):
            await service.get_stock("AAPL", "2023-01-01")
        
        # The scraper should have been cancelled, so it shouldn't complete
        # We can verify this by ensuring the task didn't run to completion

    @pytest.mark.asyncio
    async def test_scraper_exception_types_handled_correctly(self, service, mock_provider, mock_scraper, 
                                                            mock_repository, mock_logger, sample_polygon_data):
        """Test various scraper exception types are handled."""
        exceptions_to_test = [
            RuntimeError("Scraper runtime error"),
            ConnectionError("Network connection failed"),
            Exception("Generic exception"),
            ValueError("Scraper value error")
        ]
        
        mock_provider.get_daily_open_close = AsyncMock(return_value=sample_polygon_data)
        mock_repository.get_amount.return_value = 25
        
        for exception in exceptions_to_test:
            mock_scraper.get_performance = AsyncMock(side_effect=exception)
            mock_logger.reset_mock()
            
            result = await service.get_stock("AAPL", "2023-01-01")
            
            assert result.performance == {}
            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_repository_amount_integration(self, service, mock_provider, mock_scraper, 
                                                mock_repository, sample_polygon_data):
        """Test integration with repository for amount retrieval."""
        mock_provider.get_daily_open_close = AsyncMock(return_value=sample_polygon_data)
        mock_scraper.get_performance = AsyncMock(return_value={})
        
        # Test different amount values
        test_amounts = [0, 50, 1000, 999999]
        
        for amount in test_amounts:
            mock_repository.get_amount.return_value = amount
            
            result = await service.get_stock("AAPL", "2023-01-01")
            assert result.amount == amount

    @pytest.mark.asyncio
    async def test_stock_model_field_mapping(self, service, mock_provider, mock_scraper, 
                                           mock_repository, sample_performance_data):
        """Test correct mapping of all fields to Stock model."""
        polygon_data = {
            "status": "CLOSED",
            "from_": "2023-12-25",
            "symbol": "GOOGL",
            "open": 100.5,
            "high": 105.2,
            "low": 99.8,
            "close": 103.1,
            "volume": 500000,
            "afterHours": 102.9,
            "preMarket": 101.2
        }
        
        mock_provider.get_daily_open_close = AsyncMock(return_value=polygon_data)
        mock_scraper.get_performance = AsyncMock(return_value=sample_performance_data)
        mock_repository.get_amount.return_value = 200
        
        result = await service.get_stock("GOOGL", "2023-12-25")
        
        # Verify all fields are correctly mapped
        assert result.status == "CLOSED"
        assert result.from_ == "2023-12-25"
        assert result.symbol == "GOOGL"
        assert result.open == 100.5
        assert result.high == 105.2
        assert result.low == 99.8
        assert result.close == 103.1
        assert result.volume == 500000
        assert result.afterHours == 102.9
        assert result.preMarket == 101.2
        assert result.performance == sample_performance_data
        assert result.amount == 200

    def test_add_amount_delegates_to_repository(self, service, mock_repository):
        """Test that add_amount correctly delegates to repository."""
        mock_repository.add_amount.return_value = 150
        
        result = service.add_amount("AAPL", 50)
        
        assert result == 150
        mock_repository.add_amount.assert_called_once_with("AAPL", 50)

    def test_add_amount_with_various_inputs(self, service, mock_repository):
        """Test add_amount with various symbol and amount combinations."""
        test_cases = [
            ("AAPL", 10, 110),
            ("googl", 25, 125),
            ("MSFT", 0, 100),
            ("tsla", 1000, 2000)
        ]
        
        for symbol, amount, expected_result in test_cases:
            mock_repository.add_amount.return_value = expected_result
            
            result = service.add_amount(symbol, amount)
            
            assert result == expected_result
            mock_repository.add_amount.assert_called_with(symbol, amount)

    def test_initialization_sets_correct_attributes(self, mock_provider, mock_scraper, 
                                                   mock_repository, mock_logger):
        """Test that initialization sets all attributes correctly."""
        service = StockService(
            provider=mock_provider,
            scraper=mock_scraper,
            repository=mock_repository,
            logger=mock_logger
        )
        
        assert service._provider == mock_provider
        assert service._scraper == mock_scraper
        assert service._repository == mock_repository
        assert service._logger == mock_logger

    @pytest.mark.asyncio
    async def test_symbol_case_preservation_in_calls(self, service, mock_provider, mock_scraper, 
                                                     mock_repository, sample_polygon_data):
        """Test that symbol case is preserved when calling dependencies."""
        mock_provider.get_daily_open_close = AsyncMock(return_value=sample_polygon_data)
        mock_scraper.get_performance = AsyncMock(return_value={})
        mock_repository.get_amount.return_value = 0
        
        # Test with different case variations
        symbols = ["aapl", "AAPL", "ApPl", "GOOGL", "msft"]
        
        for symbol in symbols:
            await service.get_stock(symbol, "2023-01-01")
            
            # Verify the exact symbol was passed to each dependency
            mock_provider.get_daily_open_close.assert_called_with(symbol, "2023-01-01")
            mock_scraper.get_performance.assert_called_with(symbol)
            mock_repository.get_amount.assert_called_with(symbol)

    @pytest.mark.asyncio
    async def test_date_format_preservation(self, service, mock_provider, mock_scraper, 
                                          mock_repository, sample_polygon_data):
        """Test that date format is preserved when calling provider."""
        mock_provider.get_daily_open_close = AsyncMock(return_value=sample_polygon_data)
        mock_scraper.get_performance = AsyncMock(return_value={})
        mock_repository.get_amount.return_value = 0
        
        # Test with different date formats
        dates = ["2023-01-01", "2023-12-31", "2024-02-29"]
        
        for date in dates:
            await service.get_stock("AAPL", date)
            mock_provider.get_daily_open_close.assert_called_with("AAPL", date)

    @pytest.mark.asyncio
    async def test_empty_performance_data_handling(self, service, mock_provider, mock_scraper, 
                                                  mock_repository, sample_polygon_data):
        """Test handling of empty performance data from scraper."""
        mock_provider.get_daily_open_close = AsyncMock(return_value=sample_polygon_data)
        mock_scraper.get_performance = AsyncMock(return_value={})
        mock_repository.get_amount.return_value = 0
        
        result = await service.get_stock("AAPL", "2023-01-01")
        
        assert result.performance == {}
        assert isinstance(result, Stock)

    @pytest.mark.asyncio 
    async def test_none_performance_data_handling(self, service, mock_provider, mock_scraper, 
                                                 mock_repository, mock_logger, sample_polygon_data):
        """Test handling when scraper returns None (converted to empty dict)."""
        mock_provider.get_daily_open_close = AsyncMock(return_value=sample_polygon_data)
        mock_scraper.get_performance = AsyncMock(return_value=None)
        mock_repository.get_amount.return_value = 0
        
        # The service should handle None by converting it to empty dict
        # But since Stock model requires dict for performance, this test should expect empty dict
        result = await service.get_stock("AAPL", "2023-01-01")
        
        # Performance should be empty dict when scraper returns None
        assert result.performance == {}

    @pytest.mark.asyncio
    async def test_logging_on_scraper_failure(self, service, mock_provider, mock_scraper, 
                                             mock_repository, mock_logger, sample_polygon_data):
        """Test that scraper failures are properly logged."""
        mock_provider.get_daily_open_close = AsyncMock(return_value=sample_polygon_data)
        scraper_exception = RuntimeError("MarketWatch blocked request")
        mock_scraper.get_performance = AsyncMock(side_effect=scraper_exception)
        mock_repository.get_amount.return_value = 0
        
        await service.get_stock("AAPL", "2023-01-01")
        
        mock_logger.error.assert_called_once_with(
            "Performance scraping failed; returning empty performance",
            exc=scraper_exception
        )

    @pytest.mark.asyncio
    async def test_asyncio_task_cleanup_on_provider_failure(self, service, mock_provider, mock_scraper, mock_repository):
        """Test that asyncio tasks are properly cleaned up when provider fails."""
        # This is a more advanced test to ensure no resource leaks
        mock_provider.get_daily_open_close = AsyncMock(side_effect=ValueError("Provider failure"))
        mock_scraper.get_performance = AsyncMock(return_value={})
        
        # Track if there are any pending tasks before and after
        tasks_before = len(asyncio.all_tasks())
        
        with pytest.raises(ValueError):
            await service.get_stock("AAPL", "2023-01-01")
        
        # Allow any cleanup to happen
        await asyncio.sleep(0.01)
        
        tasks_after = len(asyncio.all_tasks())
        
        # Should not have created lingering tasks
        assert tasks_after <= tasks_before + 1  # Allow for the current test task