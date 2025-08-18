"""Unit tests for PolygonStockDataProvider class."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from app.integrations.PolygonStockDataProvider import PolygonStockDataProvider
from app.core.FileLogger import FileLogger


class TestPolygonStockDataProvider:
    """Test suite for PolygonStockDataProvider functionality."""

    @pytest.fixture
    def mock_logger(self):
        """Create a mock FileLogger for testing."""
        return MagicMock(spec=FileLogger)

    @pytest.fixture
    def provider(self, mock_logger):
        """Create a PolygonStockDataProvider instance for testing."""
        return PolygonStockDataProvider(
            api_key="test_key",
            timeout_seconds=5.0,
            max_retries=2,
            logger=mock_logger
        )

    @pytest.fixture
    def sample_polygon_response(self):
        """Sample valid Polygon API response."""
        return {
            "status": "OK",
            "from": "2023-01-01",
            "symbol": "AAPL",
            "open": 150.0,
            "high": 155.0,
            "low": 148.0,
            "close": 152.0,
            "volume": 1000000,
            "afterHours": 151.0,
            "preMarket": 149.0
        }

    @pytest.mark.asyncio
    async def test_successful_request(self, provider, mock_logger, sample_polygon_response):
        """Test successful API request returns correct data."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_polygon_response

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            result = await provider.get_daily_open_close("AAPL", "2023-01-01")
            
            assert result["status"] == "OK"
            assert result["symbol"] == "AAPL"
            assert result["from_"] == "2023-01-01"  # Note the renamed field
            assert result["open"] == 150.0
            assert result["high"] == 155.0
            assert result["low"] == 148.0
            assert result["close"] == 152.0
            assert result["volume"] == 1000000
            assert result["afterHours"] == 151.0
            assert result["preMarket"] == 149.0

    @pytest.mark.asyncio
    async def test_symbol_case_insensitive(self, provider, mock_logger, sample_polygon_response):
        """Test that symbol is converted to uppercase in URL."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_polygon_response

        with patch('httpx.AsyncClient') as mock_client:
            mock_get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.get = mock_get
            
            await provider.get_daily_open_close("aapl", "2023-01-01")
            
            # Verify the URL contains uppercase symbol
            call_args = mock_get.call_args
            assert "AAPL" in call_args[0][0]  # URL should contain uppercase AAPL

    @pytest.mark.asyncio
    async def test_404_error_raises_value_error(self, provider, mock_logger):
        """Test that 404 response raises ValueError."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            with pytest.raises(ValueError, match="Symbol not found or no data for date"):
                await provider.get_daily_open_close("INVALID", "2023-01-02")
                
            mock_logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_non_200_non_404_raises_runtime_error(self, provider, mock_logger):
        """Test that non-200/404 status codes raise RuntimeError."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            with pytest.raises(RuntimeError, match="Polygon error 500"):
                await provider.get_daily_open_close("AAPL", "2023-01-01")

    @pytest.mark.asyncio
    async def test_retry_logic_success_after_failure(self, provider, mock_logger, sample_polygon_response):
        """Test that retry logic works correctly after initial failures."""
        # First call fails, second succeeds
        failed_response = MagicMock()
        failed_response.status_code = 500
        failed_response.text = "Server Error"
        
        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = sample_polygon_response

        with patch('httpx.AsyncClient') as mock_client:
            mock_get = AsyncMock(side_effect=[failed_response, success_response])
            mock_client.return_value.__aenter__.return_value.get = mock_get
            
            with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
                result = await provider.get_daily_open_close("AAPL", "2023-01-01")
                
                assert result["symbol"] == "AAPL"
                assert mock_get.call_count == 2
                mock_sleep.assert_called_once_with(0.2)  # First backoff
                mock_logger.debug.assert_called()

    @pytest.mark.asyncio
    async def test_retry_exhaustion_raises_runtime_error(self, provider, mock_logger):
        """Test that after max retries, RuntimeError is raised."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Server Error"

        with patch('httpx.AsyncClient') as mock_client:
            mock_get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.get = mock_get
            
            with patch('asyncio.sleep', new_callable=AsyncMock):
                with pytest.raises(RuntimeError, match="Polygon error 500"):
                    await provider.get_daily_open_close("AAPL", "2023-01-01")
                    
                # Should attempt max_retries + 1 times (2 + 1 = 3)
                assert mock_get.call_count == 3
                mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_retry_on_404(self, provider, mock_logger):
        """Test that 404 errors don't trigger retries."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch('httpx.AsyncClient') as mock_client:
            mock_get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.get = mock_get
            
            with pytest.raises(ValueError):
                await provider.get_daily_open_close("INVALID", "2023-01-01")
                
            # Should only attempt once, no retries
            assert mock_get.call_count == 1

    @pytest.mark.asyncio
    async def test_exponential_backoff(self, provider, mock_logger):
        """Test that retry backoff increases exponentially."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Server Error"

        with patch('httpx.AsyncClient') as mock_client:
            mock_get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.get = mock_get
            
            with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
                with pytest.raises(RuntimeError):
                    await provider.get_daily_open_close("AAPL", "2023-01-01")
                
                # Check backoff times: 0.2, 0.4
                expected_calls = [((0.2,),), ((0.4,),)]
                assert mock_sleep.call_args_list == expected_calls

    @pytest.mark.asyncio
    async def test_network_exception_handling(self, provider, mock_logger):
        """Test handling of network exceptions like timeouts."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_get = AsyncMock(side_effect=httpx.TimeoutException("Request timeout"))
            mock_client.return_value.__aenter__.return_value.get = mock_get
            
            with patch('asyncio.sleep', new_callable=AsyncMock):
                with pytest.raises(RuntimeError, match="Request timeout"):
                    await provider.get_daily_open_close("AAPL", "2023-01-01")
                
                assert mock_get.call_count == 3  # max_retries + 1
                mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_missing_optional_fields(self, provider, mock_logger):
        """Test handling of missing optional fields in API response."""
        response_without_optional = {
            "status": "OK",
            "from": "2023-01-01",
            "symbol": "AAPL",
            "open": 150.0,
            "high": 155.0,
            "low": 148.0,
            "close": 152.0,
            "volume": 1000000
            # Missing afterHours and preMarket
        }
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = response_without_optional

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            result = await provider.get_daily_open_close("AAPL", "2023-01-01")
            
            assert result["afterHours"] == 0.0  # Default value
            assert result["preMarket"] == 0.0   # Default value

    @pytest.mark.asyncio
    async def test_api_key_in_request_params(self, mock_logger):
        """Test that API key is included in request parameters."""
        provider_with_key = PolygonStockDataProvider(
            api_key="test_api_key",
            timeout_seconds=5.0,
            max_retries=1,
            logger=mock_logger
        )
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "OK",
            "from": "2023-01-01",
            "symbol": "AAPL",
            "open": 150.0,
            "high": 155.0,
            "low": 148.0,
            "close": 152.0,
            "volume": 1000000
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.get = mock_get
            
            await provider_with_key.get_daily_open_close("AAPL", "2023-01-01")
            
            # Check that params include the API key
            call_args = mock_get.call_args
            assert call_args[1]['params'] == {'apiKey': 'test_api_key'}

    @pytest.mark.asyncio
    async def test_empty_api_key_no_params(self, mock_logger):
        """Test that empty API key results in no params being sent."""
        provider_no_key = PolygonStockDataProvider(
            api_key="",
            timeout_seconds=5.0,
            max_retries=1,
            logger=mock_logger
        )
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "OK",
            "from": "2023-01-01",
            "symbol": "AAPL",
            "open": 150.0,
            "high": 155.0,
            "low": 148.0,
            "close": 152.0,
            "volume": 1000000
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.get = mock_get
            
            await provider_no_key.get_daily_open_close("AAPL", "2023-01-01")
            
            # Check that params are empty
            call_args = mock_get.call_args
            assert call_args[1]['params'] == {}

    def test_initialization_sets_correct_attributes(self, mock_logger):
        """Test that initialization sets all attributes correctly."""
        provider = PolygonStockDataProvider(
            api_key="test_key",
            timeout_seconds=15.0,
            max_retries=5,
            logger=mock_logger
        )
        
        assert provider._api_key == "test_key"
        assert provider._max_retries == 5
        assert provider._logger == mock_logger
        assert isinstance(provider._timeout, httpx.Timeout)

    def test_negative_max_retries_handled(self, mock_logger):
        """Test that negative max_retries is handled correctly."""
        provider = PolygonStockDataProvider(
            api_key="test_key",
            timeout_seconds=5.0,
            max_retries=-1,
            logger=mock_logger
        )
        
        assert provider._max_retries == -1
        # The max function in get_daily_open_close should handle this