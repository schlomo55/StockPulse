from __future__ import annotations
import httpx
from bs4 import BeautifulSoup

from app.core.FileLogger import FileLogger


class MarketWatchPerformanceScraper:
    """Scrapes the PERFORMANCE section from MarketWatch stock page.

    If parsing fails due to HTML changes or missing elements, returns an empty dict
    and logs a warning. Network errors are surfaced as RuntimeError.
    """

    BASE_URL = "https://www.marketwatch.com/investing/stock/{}"
    DEFAULT_TIMEOUT = 10.0

    def __init__(self, logger: FileLogger, timeout: float = DEFAULT_TIMEOUT) -> None:
        """Initialize the MarketWatchPerformanceScraper with required dependencies.
        
        Args:
            logger: FileLogger instance for logging scraping operations and errors.
            timeout: HTTP request timeout in seconds. Defaults to DEFAULT_TIMEOUT (10.0).
        """
        self._logger = logger
        self._timeout = timeout

    async def get_performance(self, symbol: str) -> dict[str, str]:
        """Scrape performance data from MarketWatch for the given stock symbol."""
        url = self.BASE_URL.format(symbol.lower())
        try:
            # Use comprehensive browser-like headers to avoid 401 authentication errors
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Cache-Control": "max-age=0"
            }
            
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, headers=headers)
            if response.status_code != 200:
                self._logger.debug(f"MarketWatch non-200 for {symbol}: {response.status_code}")
                raise RuntimeError(f"MarketWatch error {response.status_code}")
            
            return self._parse_performance(response.text)
        except RuntimeError:
            # Propagate upstream errors (caller may decide policy)
            raise
        except Exception as exc:
            # Parse failures or other unexpected errors should not break GET entirely
            self._logger.error("MarketWatch scraping failed", exc=exc)
            return {}

    def _parse_performance(self, html: str) -> dict[str, str]:
        """Parse HTML to extract performance metrics from MarketWatch page."""
        soup = BeautifulSoup(html, "html.parser")
        
        # Strategy: find any section that looks like Performance table
        # MarketWatch often uses h3/h2 with text 'Performance'
        performance_heading = None
        for tag in soup.find_all(["h2", "h3", "span", "div"]):
            if tag.get_text(strip=True).upper() == "PERFORMANCE":
                performance_heading = tag
                break
        
        performance_table = None
        if performance_heading is not None:
            # Search for tables within vicinity of the heading
            performance_table = performance_heading.find_next("table")
        
        if performance_table is None:
            # Fallback: any table with headers matching typical performance keys
            for table in soup.find_all("table"):
                table_text = table.get_text(" ", strip=True).lower()
                if any(keyword in table_text for keyword in ["day", "week", "month", "ytd", "year"]):
                    performance_table = table
                    break
        
        performance_data: dict[str, str] = {}
        if performance_table is None:
            self._logger.debug("Performance table not found; returning empty dict")
            return performance_data
        
        # Parse table rows
        for row in performance_table.find_all("tr"):
            columns = row.find_all(["th", "td"])  # some tables use th for labels
            if len(columns) >= 2:
                key = columns[0].get_text(" ", strip=True)
                value = columns[1].get_text(" ", strip=True)
                if key and value:
                    performance_data[key] = value
        
        return performance_data