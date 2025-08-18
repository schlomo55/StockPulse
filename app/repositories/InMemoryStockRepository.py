from __future__ import annotations
from threading import RLock


class InMemoryStockRepository:
    """Thread-safe in-memory repository for stock amounts."""

    def __init__(self) -> None:
        """Initialize the InMemoryStockRepository with empty storage and thread lock.
        
        Creates an empty dictionary for storing stock amounts and a reentrant lock
        for thread-safe operations.
        """
        self._store: dict[str, int] = {}
        self._lock = RLock()

    def get_amount(self, symbol: str) -> int:
        """Get the current stored amount for a stock symbol.
        
        Args:
            symbol: Stock symbol to retrieve amount for (case-insensitive, will be converted to uppercase).
            
        Returns:
            int: Current stored amount for the symbol. Returns 0 if symbol not found.
        """
        with self._lock:
            return self._store.get(symbol.upper(), 0)

    def add_amount(self, symbol: str, amount: int) -> int:
        """Add amount to the stored total for a stock symbol and return the new total.
        
        Args:
            symbol: Stock symbol to add amount to (case-insensitive, will be converted to uppercase).
            amount: Integer amount to add to the existing total.
            
        Returns:
            int: The new total amount after addition.
        """
        with self._lock:
            key = symbol.upper()
            self._store[key] = self._store.get(key, 0) + amount
            return self._store[key]