"""Unit tests for MarketWatchPerformanceScraper class."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from app.integrations.MarketWatchPerformanceScraper import MarketWatchPerformanceScraper
from app.core.FileLogger import FileLogger


class TestMarketWatchPerformanceScraper:
    """Test suite for MarketWatchPerformanceScraper functionality."""

    @pytest.fixture
    def mock_logger(self):
        """Create a mock FileLogger for testing."""
        return MagicMock(spec=FileLogger)

    @pytest.fixture
    def scraper(self, mock_logger):
        """Create a MarketWatchPerformanceScraper instance for testing."""
        return MarketWatchPerformanceScraper(logger=mock_logger, timeout=5.0)

    @pytest.fixture
    def sample_html_with_performance_table(self):
        """Sample HTML with a performance table."""
        return """
        <html>
        <body>
            <h3>PERFORMANCE</h3>
            <table>
                <tr><th>5 Day</th><td>+2.5%</td></tr>
                <tr><th>1 Month</th><td>+5.1%</td></tr>
                <tr><th>3 Month</th><td>-1.2%</td></tr>
                <tr><th>YTD</th><td>+15.7%</td></tr>
                <tr><th>1 Year</th><td>+22.3%</td></tr>
            </table>
        </body>
        </html>
        """

    @pytest.fixture
    def sample_html_no_performance(self):
        """Sample HTML without performance data."""
        return """
        <html>
        <body>
            <h3>Other Section</h3>
            <table>
                <tr><th>Revenue</th><td>$100M</td></tr>
            </table>
        </body>
        </html>
        """

    @pytest.mark.asyncio
    async def test_successful_scraping_with_h3_performance(self, scraper, mock_logger, sample_html_with_performance_table):
        """Test successful scraping when performance section has h3 heading."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = sample_html_with_performance_table

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            result = await scraper.get_performance("AAPL")
            
            assert result["5 Day"] == "+2.5%"
            assert result["1 Month"] == "+5.1%"
            assert result["3 Month"] == "-1.2%"
            assert result["YTD"] == "+15.7%"
            assert result["1 Year"] == "+22.3%"

    @pytest.mark.asyncio
    async def test_successful_scraping_with_h2_performance(self, scraper, mock_logger):
        """Test successful scraping when performance section has h2 heading."""
        html_with_h2 = """
        <html>
        <body>
            <h2>Performance</h2>
            <table>
                <tr><td>5 Day</td><td>+1.5%</td></tr>
                <tr><td>1 Week</td><td>+3.2%</td></tr>
            </table>
        </body>
        </html>
        """
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html_with_h2

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            result = await scraper.get_performance("AAPL")
            
            assert result["5 Day"] == "+1.5%"
            assert result["1 Week"] == "+3.2%"

    @pytest.mark.asyncio
    async def test_fallback_table_detection(self, scraper, mock_logger):
        """Test fallback table detection when no performance heading is found."""
        html_no_heading = """
        <html>
        <body>
            <table>
                <tr><td>5 Day Return</td><td>+2.1%</td></tr>
                <tr><td>1 Month Performance</td><td>+4.5%</td></tr>
                <tr><td>YTD Growth</td><td>+12.3%</td></tr>
            </table>
        </body>
        </html>
        """
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html_no_heading

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            result = await scraper.get_performance("AAPL")
            
            assert result["5 Day Return"] == "+2.1%"
            assert result["1 Month Performance"] == "+4.5%"
            assert result["YTD Growth"] == "+12.3%"

    @pytest.mark.asyncio
    async def test_no_performance_table_returns_empty_dict(self, scraper, mock_logger, sample_html_no_performance):
        """Test that missing performance table returns empty dict."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = sample_html_no_performance

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            result = await scraper.get_performance("AAPL")
            
            assert result == {}
            mock_logger.debug.assert_called_with("Performance table not found; returning empty dict")

    @pytest.mark.asyncio
    async def test_401_authentication_error_raises_runtime_error(self, scraper, mock_logger):
        """Test that 401 status code raises RuntimeError."""
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            with pytest.raises(RuntimeError, match="MarketWatch error 401"):
                await scraper.get_performance("AAPL")
                
            mock_logger.debug.assert_called()

    @pytest.mark.asyncio
    async def test_404_error_raises_runtime_error(self, scraper, mock_logger):
        """Test that 404 status code raises RuntimeError."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            with pytest.raises(RuntimeError, match="MarketWatch error 404"):
                await scraper.get_performance("INVALID")

    @pytest.mark.asyncio
    async def test_network_timeout_exception_returns_empty_dict(self, scraper, mock_logger):
        """Test that network timeouts are handled gracefully."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.TimeoutException("Request timeout")
            )
            
            result = await scraper.get_performance("AAPL")
            
            assert result == {}
            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_network_connection_error_returns_empty_dict(self, scraper, mock_logger):
        """Test that network connection errors are handled gracefully."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection failed")
            )
            
            result = await scraper.get_performance("AAPL")
            
            assert result == {}
            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_malformed_html_returns_empty_dict(self, scraper, mock_logger):
        """Test that malformed HTML is handled gracefully."""
        malformed_html = "<html><body><h3>PERFORMANCE</h3><table><tr><td>broken"
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = malformed_html

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            result = await scraper.get_performance("AAPL")
            
            # BeautifulSoup should still parse it, but might not find proper table structure
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_empty_html_returns_empty_dict(self, scraper, mock_logger):
        """Test that empty HTML returns empty dict."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = ""

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            result = await scraper.get_performance("AAPL")
            
            assert result == {}

    @pytest.mark.asyncio
    async def test_table_with_mixed_th_td_elements(self, scraper, mock_logger):
        """Test parsing table with mixed th and td elements."""
        mixed_table_html = """
        <html>
        <body>
            <h3>PERFORMANCE</h3>
            <table>
                <tr><th>5 Day</th><td>+1.5%</td></tr>
                <tr><td>1 Month</td><td>+3.2%</td></tr>
                <tr><th>YTD</th><th>+15.7%</th></tr>
            </table>
        </body>
        </html>
        """
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = mixed_table_html

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            result = await scraper.get_performance("AAPL")
            
            assert result["5 Day"] == "+1.5%"
            assert result["1 Month"] == "+3.2%"
            # Note: YTD row has th for both columns, so second th becomes the value

    @pytest.mark.asyncio
    async def test_table_with_insufficient_columns(self, scraper, mock_logger):
        """Test table rows with insufficient columns are skipped."""
        insufficient_columns_html = """
        <html>
        <body>
            <h3>PERFORMANCE</h3>
            <table>
                <tr><td>5 Day</td><td>+1.5%</td></tr>
                <tr><td>Single Column</td></tr>
                <tr><td>1 Month</td><td>+3.2%</td></tr>
            </table>
        </body>
        </html>
        """
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = insufficient_columns_html

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            result = await scraper.get_performance("AAPL")
            
            assert result["5 Day"] == "+1.5%"
            assert result["1 Month"] == "+3.2%"
            assert "Single Column" not in result

    @pytest.mark.asyncio
    async def test_table_with_empty_cells(self, scraper, mock_logger):
        """Test table with empty cells are filtered out."""
        empty_cells_html = """
        <html>
        <body>
            <h3>PERFORMANCE</h3>
            <table>
                <tr><td>5 Day</td><td>+1.5%</td></tr>
                <tr><td></td><td>+3.2%</td></tr>
                <tr><td>1 Month</td><td></td></tr>
                <tr><td>YTD</td><td>+15.7%</td></tr>
            </table>
        </body>
        </html>
        """
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = empty_cells_html

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            result = await scraper.get_performance("AAPL")
            
            assert result["5 Day"] == "+1.5%"
            assert result["YTD"] == "+15.7%"
            # Rows with empty key or value should be filtered out
            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_symbol_case_conversion_in_url(self, scraper, mock_logger, sample_html_with_performance_table):
        """Test that symbol is converted to lowercase in URL."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = sample_html_with_performance_table

        with patch('httpx.AsyncClient') as mock_client:
            mock_get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.get = mock_get
            
            await scraper.get_performance("AAPL")
            
            # Verify URL contains lowercase symbol
            call_args = mock_get.call_args
            assert "aapl" in call_args[0][0]  # URL should contain lowercase aapl

    @pytest.mark.asyncio
    async def test_comprehensive_browser_headers_sent(self, scraper, mock_logger, sample_html_with_performance_table):
        """Test that comprehensive browser-like headers are sent."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = sample_html_with_performance_table

        with patch('httpx.AsyncClient') as mock_client:
            mock_get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.get = mock_get
            
            await scraper.get_performance("AAPL")
            
            # Verify headers were sent
            call_args = mock_get.call_args
            headers = call_args[1]['headers']
            assert 'User-Agent' in headers
            assert 'Mozilla' in headers['User-Agent']
            assert 'Accept' in headers
            assert 'Accept-Language' in headers

    @pytest.mark.asyncio
    async def test_performance_heading_case_insensitive(self, scraper, mock_logger):
        """Test that performance heading detection is case insensitive."""
        case_variations_html = """
        <html>
        <body>
            <h3>performance</h3>
            <table>
                <tr><td>5 Day</td><td>+1.5%</td></tr>
            </table>
        </body>
        </html>
        """
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = case_variations_html

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            result = await scraper.get_performance("AAPL")
            
            assert result["5 Day"] == "+1.5%"

    @pytest.mark.asyncio
    async def test_multiple_performance_tables_uses_first(self, scraper, mock_logger):
        """Test that when multiple performance sections exist, first one is used."""
        multiple_tables_html = """
        <html>
        <body>
            <h3>PERFORMANCE</h3>
            <table>
                <tr><td>5 Day</td><td>+1.5%</td></tr>
            </table>
            <h3>PERFORMANCE</h3>
            <table>
                <tr><td>5 Day</td><td>+2.5%</td></tr>
            </table>
        </body>
        </html>
        """
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = multiple_tables_html

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            result = await scraper.get_performance("AAPL")
            
            assert result["5 Day"] == "+1.5%"  # Should use first table

    def test_initialization_sets_correct_attributes(self, mock_logger):
        """Test that initialization sets all attributes correctly."""
        scraper = MarketWatchPerformanceScraper(logger=mock_logger, timeout=15.0)
        
        assert scraper._logger == mock_logger
        assert scraper._timeout == 15.0

    def test_initialization_uses_default_timeout(self, mock_logger):
        """Test that initialization uses default timeout when not specified."""
        scraper = MarketWatchPerformanceScraper(logger=mock_logger)
        
        assert scraper._timeout == MarketWatchPerformanceScraper.DEFAULT_TIMEOUT

    @pytest.mark.asyncio
    async def test_runtime_error_propagated_upstream(self, scraper, mock_logger):
        """Test that RuntimeError from HTTP status is propagated upstream."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            # Should propagate RuntimeError, not catch it
            with pytest.raises(RuntimeError, match="MarketWatch error 500"):
                await scraper.get_performance("AAPL")