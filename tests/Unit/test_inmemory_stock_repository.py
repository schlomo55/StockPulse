"""Unit tests for InMemoryStockRepository class."""

import pytest
import threading
import time
import concurrent.futures
from app.repositories.InMemoryStockRepository import InMemoryStockRepository


class TestInMemoryStockRepository:
    """Test suite for InMemoryStockRepository functionality."""

    @pytest.fixture
    def repository(self):
        """Create a fresh InMemoryStockRepository instance for testing."""
        return InMemoryStockRepository()

    def test_initialization_creates_empty_storage(self, repository):
        """Test that initialization creates empty storage."""
        # Repository should start empty
        assert repository.get_amount("AAPL") == 0
        assert repository.get_amount("GOOGL") == 0

    def test_initialization_creates_lock(self, repository):
        """Test that initialization creates a threading lock."""
        assert hasattr(repository, '_lock')
        assert hasattr(repository, '_store')
        assert repository._store == {}

    def test_get_amount_returns_zero_for_new_symbol(self, repository):
        """Test that get_amount returns 0 for symbols not in storage."""
        assert repository.get_amount("AAPL") == 0
        assert repository.get_amount("GOOGL") == 0
        assert repository.get_amount("NONEXISTENT") == 0

    def test_get_amount_case_insensitive(self, repository):
        """Test that get_amount is case insensitive."""
        # Add amount with uppercase
        repository.add_amount("AAPL", 100)
        
        # Should return same amount regardless of case
        assert repository.get_amount("AAPL") == 100
        assert repository.get_amount("aapl") == 100
        assert repository.get_amount("Aapl") == 100
        assert repository.get_amount("AaPl") == 100

    def test_add_amount_new_symbol(self, repository):
        """Test adding amount to a new symbol."""
        result = repository.add_amount("AAPL", 50)
        
        assert result == 50
        assert repository.get_amount("AAPL") == 50

    def test_add_amount_existing_symbol(self, repository):
        """Test adding amount to an existing symbol."""
        repository.add_amount("AAPL", 50)
        result = repository.add_amount("AAPL", 30)
        
        assert result == 80
        assert repository.get_amount("AAPL") == 80

    def test_add_amount_zero_value(self, repository):
        """Test adding zero amount."""
        result = repository.add_amount("AAPL", 0)
        
        assert result == 0
        assert repository.get_amount("AAPL") == 0
        
        # Add some amount first
        repository.add_amount("AAPL", 100)
        result = repository.add_amount("AAPL", 0)
        
        assert result == 100  # Should remain unchanged

    def test_add_amount_negative_value(self, repository):
        """Test adding negative amount (subtraction)."""
        # Start with some amount
        repository.add_amount("AAPL", 100)
        
        # Subtract amount
        result = repository.add_amount("AAPL", -30)
        
        assert result == 70
        assert repository.get_amount("AAPL") == 70

    def test_add_amount_negative_resulting_in_negative_total(self, repository):
        """Test that adding negative amount can result in negative total."""
        repository.add_amount("AAPL", 50)
        result = repository.add_amount("AAPL", -100)
        
        assert result == -50
        assert repository.get_amount("AAPL") == -50

    def test_add_amount_case_insensitive(self, repository):
        """Test that add_amount is case insensitive."""
        repository.add_amount("AAPL", 50)
        repository.add_amount("aapl", 30)
        repository.add_amount("Aapl", 20)
        
        # All should add to the same symbol
        assert repository.get_amount("AAPL") == 100
        assert repository.get_amount("aapl") == 100

    def test_add_amount_returns_new_total(self, repository):
        """Test that add_amount returns the new total amount."""
        result1 = repository.add_amount("AAPL", 25)
        assert result1 == 25
        
        result2 = repository.add_amount("AAPL", 35)
        assert result2 == 60
        
        result3 = repository.add_amount("AAPL", -10)
        assert result3 == 50

    def test_multiple_symbols_independent(self, repository):
        """Test that different symbols maintain independent amounts."""
        repository.add_amount("AAPL", 100)
        repository.add_amount("GOOGL", 200)
        repository.add_amount("MSFT", 150)
        
        assert repository.get_amount("AAPL") == 100
        assert repository.get_amount("GOOGL") == 200
        assert repository.get_amount("MSFT") == 150
        
        # Modify one symbol
        repository.add_amount("AAPL", 50)
        
        # Others should remain unchanged
        assert repository.get_amount("AAPL") == 150
        assert repository.get_amount("GOOGL") == 200
        assert repository.get_amount("MSFT") == 150

    def test_large_amounts(self, repository):
        """Test handling of large amounts."""
        large_amount = 1_000_000_000
        
        result = repository.add_amount("AAPL", large_amount)
        assert result == large_amount
        assert repository.get_amount("AAPL") == large_amount
        
        # Add more
        result = repository.add_amount("AAPL", large_amount)
        assert result == 2 * large_amount

    def test_thread_safety_concurrent_reads(self, repository):
        """Test that concurrent reads are thread-safe."""
        # Pre-populate with some data
        repository.add_amount("AAPL", 1000)
        
        num_threads = 50
        results = []
        
        def read_amount():
            amount = repository.get_amount("AAPL")
            results.append(amount)
        
        threads = []
        for _ in range(num_threads):
            thread = threading.Thread(target=read_amount)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # All reads should return the same value
        assert len(results) == num_threads
        assert all(result == 1000 for result in results)

    def test_thread_safety_concurrent_writes(self, repository):
        """Test that concurrent writes are thread-safe."""
        num_threads = 20
        amount_per_thread = 10
        
        def add_amounts(thread_id):
            for _ in range(amount_per_thread):
                repository.add_amount("AAPL", 1)
        
        threads = []
        for thread_id in range(num_threads):
            thread = threading.Thread(target=add_amounts, args=(thread_id,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Final amount should be exactly num_threads * amount_per_thread
        expected_total = num_threads * amount_per_thread
        assert repository.get_amount("AAPL") == expected_total

    def test_thread_safety_mixed_operations(self, repository):
        """Test thread safety with mixed read/write operations."""
        num_readers = 10
        num_writers = 10
        writes_per_thread = 5
        
        # Pre-populate
        repository.add_amount("AAPL", 100)
        
        results = []
        
        def reader_thread():
            for _ in range(10):  # Multiple reads per thread
                amount = repository.get_amount("AAPL")
                results.append(amount)
                time.sleep(0.001)  # Small delay to increase chance of race conditions
        
        def writer_thread():
            for _ in range(writes_per_thread):
                repository.add_amount("AAPL", 1)
                time.sleep(0.001)
        
        threads = []
        
        # Start reader threads
        for _ in range(num_readers):
            thread = threading.Thread(target=reader_thread)
            threads.append(thread)
            thread.start()
        
        # Start writer threads
        for _ in range(num_writers):
            thread = threading.Thread(target=writer_thread)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Final amount should be predictable
        expected_final = 100 + (num_writers * writes_per_thread)
        assert repository.get_amount("AAPL") == expected_final
        
        # All read results should be valid (non-negative and reasonable)
        assert len(results) > 0
        assert all(isinstance(result, int) for result in results)
        assert all(result >= 100 for result in results)  # Should be at least initial amount
        assert all(result <= expected_final for result in results)  # Should not exceed final

    def test_thread_safety_different_symbols(self, repository):
        """Test thread safety when different threads access different symbols."""
        symbols = ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN"]
        amount_per_symbol = 100
        
        def add_to_symbol(symbol):
            for _ in range(amount_per_symbol):
                repository.add_amount(symbol, 1)
        
        threads = []
        for symbol in symbols:
            thread = threading.Thread(target=add_to_symbol, args=(symbol,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Each symbol should have the expected amount
        for symbol in symbols:
            assert repository.get_amount(symbol) == amount_per_symbol

    def test_thread_safety_same_symbol_case_variations(self, repository):
        """Test thread safety with case variations of the same symbol."""
        case_variations = ["AAPL", "aapl", "Aapl", "aApL", "AAPL"]
        threads_per_variation = 5
        amount_per_thread = 10
        
        def add_amounts(symbol_case):
            for _ in range(amount_per_thread):
                repository.add_amount(symbol_case, 1)
        
        threads = []
        for variation in case_variations:
            for _ in range(threads_per_variation):
                thread = threading.Thread(target=add_amounts, args=(variation,))
                threads.append(thread)
                thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # All variations should contribute to the same symbol
        total_threads = len(case_variations) * threads_per_variation
        expected_total = total_threads * amount_per_thread
        
        assert repository.get_amount("AAPL") == expected_total
        assert repository.get_amount("aapl") == expected_total

    def test_concurrent_futures_stress_test(self, repository):
        """Stress test using concurrent.futures for higher concurrency."""
        num_workers = 50
        operations_per_worker = 20
        
        def worker_operations(worker_id):
            symbol = f"STOCK{worker_id % 5}"  # Use 5 different symbols
            total_added = 0
            
            for i in range(operations_per_worker):
                amount_to_add = i + 1  # Add increasing amounts
                repository.add_amount(symbol, amount_to_add)
                total_added += amount_to_add
            
            return symbol, total_added
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            # Submit all tasks
            futures = [
                executor.submit(worker_operations, worker_id)
                for worker_id in range(num_workers)
            ]
            
            # Collect results
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # Verify results
        symbol_totals = {}
        for symbol, added_amount in results:
            symbol_totals[symbol] = symbol_totals.get(symbol, 0) + added_amount
        
        # Check that repository amounts match expected totals
        for symbol, expected_total in symbol_totals.items():
            actual_total = repository.get_amount(symbol)
            assert actual_total == expected_total

    def test_symbol_storage_key_normalization(self, repository):
        """Test that symbols are consistently stored in uppercase."""
        test_symbols = ["aapl", "AAPL", "Aapl", "aApL", "GOOGL", "googl"]
        
        for symbol in test_symbols:
            repository.add_amount(symbol, 10)
        
        # Check internal storage (accessing private attribute for verification)
        stored_keys = list(repository._store.keys())
        
        # All keys should be uppercase
        assert all(key.isupper() for key in stored_keys)
        
        # Should only have unique symbols
        expected_symbols = {"AAPL", "GOOGL"}
        assert set(stored_keys) == expected_symbols

    def test_edge_case_empty_symbol(self, repository):
        """Test handling of empty symbol string."""
        result = repository.add_amount("", 100)
        assert result == 100
        assert repository.get_amount("") == 100

    def test_edge_case_whitespace_symbol(self, repository):
        """Test handling of symbols with whitespace."""
        symbols_with_whitespace = [" AAPL", "AAPL ", " AAPL ", "  AAPL  "]
        
        for symbol in symbols_with_whitespace:
            repository.add_amount(symbol, 25)
        
        # Each should be treated as separate symbols (no automatic trimming)
        for symbol in symbols_with_whitespace:
            assert repository.get_amount(symbol) == 25

    def test_edge_case_special_characters_in_symbol(self, repository):
        """Test handling of symbols with special characters."""
        special_symbols = ["BRK.A", "BRK-B", "SPY@", "STOCK$", "FUND#1", "TEST_SYMBOL"]
        
        for symbol in special_symbols:
            repository.add_amount(symbol, 50)
            assert repository.get_amount(symbol) == 50

    def test_performance_large_dataset(self, repository):
        """Test performance with a large dataset."""
        num_symbols = 1000
        operations_per_symbol = 10
        
        # Add amounts to many symbols
        for i in range(num_symbols):
            symbol = f"STOCK{i:04d}"
            for j in range(operations_per_symbol):
                repository.add_amount(symbol, j + 1)
        
        # Verify a sample of results
        for i in range(0, num_symbols, 100):  # Check every 100th symbol
            symbol = f"STOCK{i:04d}"
            expected_total = sum(range(1, operations_per_symbol + 1))  # 1+2+3+...+operations_per_symbol
            assert repository.get_amount(symbol) == expected_total

    def test_repository_isolation(self):
        """Test that different repository instances are isolated."""
        repo1 = InMemoryStockRepository()
        repo2 = InMemoryStockRepository()
        
        repo1.add_amount("AAPL", 100)
        repo2.add_amount("AAPL", 200)
        
        assert repo1.get_amount("AAPL") == 100
        assert repo2.get_amount("AAPL") == 200

    def test_memory_efficiency_duplicate_operations(self, repository):
        """Test memory efficiency with duplicate operations on same symbols."""
        # Perform many operations on the same few symbols
        symbols = ["AAPL", "GOOGL", "MSFT"]
        operations_per_symbol = 1000
        
        for _ in range(operations_per_symbol):
            for symbol in symbols:
                repository.add_amount(symbol, 1)
        
        # Should only store 3 symbols despite 3000 operations
        assert len(repository._store) == 3
        
        for symbol in symbols:
            assert repository.get_amount(symbol) == operations_per_symbol

    def test_thread_safety_rapid_alternating_operations(self, repository):
        """Test thread safety with rapid alternating operations."""
        num_threads = 20
        operations_per_thread = 100
        
        def alternating_operations(thread_id):
            symbol = "AAPL"
            for i in range(operations_per_thread):
                if i % 2 == 0:
                    repository.add_amount(symbol, 1)
                else:
                    # Just read the current amount
                    current = repository.get_amount(symbol)
                    # Ensure we got a valid integer
                    assert isinstance(current, int)
                    assert current >= 0
        
        threads = []
        for thread_id in range(num_threads):
            thread = threading.Thread(target=alternating_operations, args=(thread_id,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Calculate expected result: each thread does operations_per_thread/2 additions
        # (assuming operations_per_thread is even)
        expected_additions_per_thread = operations_per_thread // 2
        expected_total = num_threads * expected_additions_per_thread
        
        assert repository.get_amount("AAPL") == expected_total

    def test_return_value_consistency(self, repository):
        """Test that return values are consistent with stored values."""
        test_cases = [
            ("AAPL", 0, 0),      # Starting from 0
            ("AAPL", 100, 100),  # First addition
            ("AAPL", 50, 150),   # Second addition
            ("AAPL", -25, 125),  # Subtraction
            ("GOOGL", 200, 200), # Different symbol
            ("GOOGL", 75, 275),  # Add to second symbol
        ]
        
        for symbol, amount_to_add, expected_result in test_cases:
            result = repository.add_amount(symbol, amount_to_add)
            assert result == expected_result
            assert repository.get_amount(symbol) == expected_result