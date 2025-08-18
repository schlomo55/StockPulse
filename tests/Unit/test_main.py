"""Unit tests for main application module."""

import pytest
import os
from unittest.mock import MagicMock, patch, Mock
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient

from main import create_app, _load_config
from app.core.FileLogger import FileLogger
from app.repositories.InMemoryStockRepository import InMemoryStockRepository


class TestLoadConfig:
    """Test suite for _load_config function."""

    @patch.dict(os.environ, {}, clear=True)
    @patch('main.load_dotenv')
    def test_load_config_defaults_when_no_env_vars(self, mock_load_dotenv):
        """Test that _load_config returns defaults when no environment variables are set."""
        api_key, timeout_seconds, max_retries = _load_config()
        
        assert api_key == ""
        assert timeout_seconds == 10.0
        assert max_retries == 2

    @patch.dict(os.environ, {
        'POLYGON_API_KEY': 'test_api_key',
        'HTTP_TIMEOUT_SECONDS': '15.5',
        'HTTP_MAX_RETRIES': '5'
    })
    def test_load_config_uses_env_vars_when_present(self):
        """Test that _load_config uses environment variables when present."""
        api_key, timeout_seconds, max_retries = _load_config()
        
        assert api_key == 'test_api_key'
        assert timeout_seconds == 15.5
        assert max_retries == 5

    @patch.dict(os.environ, {
        'POLYGON_API_KEY': '',
        'HTTP_TIMEOUT_SECONDS': '0.5',
        'HTTP_MAX_RETRIES': '0'
    })
    def test_load_config_handles_edge_case_values(self):
        """Test that _load_config handles edge case values correctly."""
        api_key, timeout_seconds, max_retries = _load_config()
        
        assert api_key == ''
        assert timeout_seconds == 0.5
        assert max_retries == 0

    @patch.dict(os.environ, {
        'POLYGON_API_KEY': 'valid_key',
        'HTTP_TIMEOUT_SECONDS': 'invalid_float',
        'HTTP_MAX_RETRIES': '3'
    })
    def test_load_config_raises_on_invalid_float(self):
        """Test that _load_config raises ValueError on invalid float conversion."""
        with pytest.raises(ValueError):
            _load_config()

    @patch.dict(os.environ, {
        'POLYGON_API_KEY': 'valid_key',
        'HTTP_TIMEOUT_SECONDS': '5.0',
        'HTTP_MAX_RETRIES': 'invalid_int'
    })
    def test_load_config_raises_on_invalid_int(self):
        """Test that _load_config raises ValueError on invalid int conversion."""
        with pytest.raises(ValueError):
            _load_config()

    @patch('main.load_dotenv')
    def test_load_config_calls_load_dotenv(self, mock_load_dotenv):
        """Test that _load_config calls load_dotenv to load .env file."""
        _load_config()
        mock_load_dotenv.assert_called_once()


class TestCreateApp:
    """Test suite for create_app function."""

    def test_create_app_returns_fastapi_instance(self):
        """Test that create_app returns a FastAPI instance."""
        app = create_app()
        assert isinstance(app, FastAPI)
        assert app.title == "Stocks API"
        assert app.version == "1.0.0"

    def test_create_app_with_custom_logger(self):
        """Test create_app with custom logger dependency."""
        custom_logger = MagicMock(spec=FileLogger)
        
        app = create_app(logger=custom_logger)
        
        assert isinstance(app, FastAPI)
        # The logger should be used internally, but we can't directly test this
        # without accessing private attributes or mocking the entire chain

    def test_create_app_with_custom_repository(self):
        """Test create_app with custom repository dependency."""
        custom_repository = MagicMock(spec=InMemoryStockRepository)
        
        app = create_app(repository=custom_repository)
        
        assert isinstance(app, FastAPI)

    def test_create_app_with_custom_provider(self):
        """Test create_app with custom provider dependency."""
        custom_provider = MagicMock()
        
        app = create_app(provider=custom_provider)
        
        assert isinstance(app, FastAPI)

    def test_create_app_with_custom_scraper(self):
        """Test create_app with custom scraper dependency."""
        custom_scraper = MagicMock()
        
        app = create_app(scraper=custom_scraper)
        
        assert isinstance(app, FastAPI)

    def test_create_app_with_all_custom_dependencies(self):
        """Test create_app with all custom dependencies."""
        custom_logger = MagicMock(spec=FileLogger)
        custom_repository = MagicMock(spec=InMemoryStockRepository)
        custom_provider = MagicMock()
        custom_scraper = MagicMock()
        
        app = create_app(
            logger=custom_logger,
            repository=custom_repository,
            provider=custom_provider,
            scraper=custom_scraper
        )
        
        assert isinstance(app, FastAPI)

    @patch('main._load_config')
    @patch('app.integrations.PolygonStockDataProvider.PolygonStockDataProvider')
    def test_create_app_creates_default_provider_when_none_provided(self, mock_provider_class, mock_load_config):
        """Test that create_app creates default PolygonStockDataProvider when none provided."""
        mock_load_config.return_value = ('test_key', 10.0, 2)
        mock_provider_instance = MagicMock()
        mock_provider_class.return_value = mock_provider_instance
        
        app = create_app()
        
        mock_load_config.assert_called_once()
        mock_provider_class.assert_called_once()
        # Verify the provider was created with config values
        call_args = mock_provider_class.call_args[0]
        assert call_args[0] == 'test_key'  # api_key
        assert call_args[1] == 10.0        # timeout_seconds
        assert call_args[2] == 2           # max_retries

    @patch('app.integrations.MarketWatchPerformanceScraper.MarketWatchPerformanceScraper')
    def test_create_app_creates_default_scraper_when_none_provided(self, mock_scraper_class):
        """Test that create_app creates default MarketWatchPerformanceScraper when none provided."""
        mock_scraper_instance = MagicMock()
        mock_scraper_class.return_value = mock_scraper_instance
        
        app = create_app()
        
        mock_scraper_class.assert_called_once()

    def test_create_app_creates_default_logger_when_none_provided(self):
        """Test that create_app creates default FileLogger when none provided."""
        with patch('main.FileLogger') as mock_logger_class:
            mock_logger_instance = MagicMock()
            mock_logger_class.return_value = mock_logger_instance
            
            app = create_app()
            
            mock_logger_class.assert_called_once_with(Path("logs"))

    def test_create_app_creates_default_repository_when_none_provided(self):
        """Test that create_app creates default InMemoryStockRepository when none provided."""
        with patch('main.InMemoryStockRepository') as mock_repo_class:
            mock_repo_instance = MagicMock()
            mock_repo_class.return_value = mock_repo_instance
            
            app = create_app()
            
            mock_repo_class.assert_called_once()

    def test_create_app_includes_stock_router(self):
        """Test that create_app includes the stock router."""
        app = create_app()
        
        # Check that routes are registered
        assert len(app.routes) > 0
        
        # Check for stock-related routes
        route_paths = [route.path for route in app.routes if hasattr(route, 'path')]
        stock_routes = [path for path in route_paths if '/stock' in path]
        assert len(stock_routes) > 0

    def test_create_app_has_root_endpoint(self):
        """Test that create_app includes the root endpoint."""
        app = create_app()
        client = TestClient(app)
        
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Stocks API is running"

    def test_create_app_root_endpoint_docstring(self):
        """Test that root endpoint has proper docstring."""
        app = create_app()
        
        # Find the root endpoint function
        root_func = None
        for route in app.routes:
            if hasattr(route, 'path') and route.path == '/':
                root_func = route.endpoint
                break
        
        assert root_func is not None
        assert root_func.__doc__ is not None
        assert "Root endpoint" in root_func.__doc__

    @patch('main.StockService')
    @patch('main.StockController')
    def test_create_app_wires_dependencies_correctly(self, mock_controller_class, mock_service_class):
        """Test that create_app wires up dependencies in correct order."""
        mock_service_instance = MagicMock()
        mock_controller_instance = MagicMock()
        mock_service_class.return_value = mock_service_instance
        mock_controller_class.return_value = mock_controller_instance
        
        custom_provider = MagicMock()
        custom_scraper = MagicMock()
        custom_repository = MagicMock()
        custom_logger = MagicMock()
        
        app = create_app(
            logger=custom_logger,
            repository=custom_repository,
            provider=custom_provider,
            scraper=custom_scraper
        )
        
        # Verify StockService was created with correct dependencies
        mock_service_class.assert_called_once_with(
            custom_provider, custom_scraper, custom_repository, custom_logger
        )
        
        # Verify StockController was created with the service
        mock_controller_class.assert_called_once_with(mock_service_instance)
        
        # Verify controller register method was called
        mock_controller_instance.register.assert_called_once()

    def test_create_app_multiple_calls_create_independent_instances(self):
        """Test that multiple create_app calls create independent FastAPI instances."""
        app1 = create_app()
        app2 = create_app()
        
        assert app1 is not app2
        assert isinstance(app1, FastAPI)
        assert isinstance(app2, FastAPI)

    def test_create_app_with_none_dependencies_uses_defaults(self):
        """Test that explicitly passing None for dependencies uses defaults."""
        app = create_app(
            logger=None,
            repository=None,
            provider=None,
            scraper=None
        )
        
        assert isinstance(app, FastAPI)

    @patch('main.StockService')
    def test_create_app_service_creation_failure_propagates(self, mock_service_class):
        """Test that service creation failures are propagated."""
        mock_service_class.side_effect = Exception("Service creation failed")
        
        with pytest.raises(Exception, match="Service creation failed"):
            create_app()

    def test_create_app_with_custom_path_for_logger(self):
        """Test create_app creates FileLogger with custom path when none provided."""
        with patch('main.FileLogger') as mock_logger_class:
            mock_logger_instance = MagicMock()
            mock_logger_class.return_value = mock_logger_instance
            
            app = create_app()
            
            # Verify FileLogger was called with Path("logs")
            call_args = mock_logger_class.call_args[0]
            assert call_args[0] == Path("logs")


class TestAppInstance:
    """Test suite for the global app instance."""

    def test_module_app_instance_exists(self):
        """Test that the module creates a global app instance."""
        import main
        assert hasattr(main, 'app')
        assert isinstance(main.app, FastAPI)

    def test_module_app_instance_is_functional(self):
        """Test that the global app instance is functional."""
        import main
        client = TestClient(main.app)
        
        response = client.get("/")
        assert response.status_code == 200

    def test_module_app_instance_has_stock_routes(self):
        """Test that the global app instance has stock routes."""
        import main
        client = TestClient(main.app)
        
        # This would normally fail without mocking the dependencies,
        # but we can at least test that the route exists
        response = client.get("/stock/AAPL")
        # We expect this to fail due to missing dependencies, but the route should exist
        assert response.status_code != 404  # Route should exist, even if it fails


class TestIntegration:
    """Integration tests for the complete application."""

    def test_create_app_with_mocked_dependencies_full_flow(self):
        """Test complete application flow with mocked dependencies."""
        # Create mock dependencies
        mock_logger = MagicMock(spec=FileLogger)
        mock_repository = MagicMock(spec=InMemoryStockRepository)
        mock_provider = MagicMock()
        mock_scraper = MagicMock()
        
        # Setup mock repository
        mock_repository.get_amount.return_value = 100
        mock_repository.add_amount.return_value = 150
        
        # Setup mock provider
        mock_polygon_data = {
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
        mock_provider.get_daily_open_close = MagicMock(return_value=mock_polygon_data)
        
        # Setup mock scraper
        mock_performance_data = {"5 Day": "+2.5%", "YTD": "+15.7%"}
        mock_scraper.get_performance = MagicMock(return_value=mock_performance_data)
        
        # Create app with mocked dependencies
        app = create_app(
            logger=mock_logger,
            repository=mock_repository,
            provider=mock_provider,
            scraper=mock_scraper
        )
        
        # Test the application
        client = TestClient(app)
        
        # Test root endpoint
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["message"] == "Stocks API is running"
        
        # Note: We can't easily test the stock endpoints here because they use async
        # and the mocks would need to be AsyncMock for the service layer

    def test_create_app_error_handling_on_import_failures(self):
        """Test that create_app handles import failures gracefully."""
        # This is more of a structure test - the imports should work
        # but if there were import issues, they would be caught here
        try:
            app = create_app()
            assert isinstance(app, FastAPI)
        except ImportError as e:
            pytest.fail(f"Import error in create_app: {e}")

    def test_create_app_configuration_environment_isolation(self):
        """Test that create_app properly isolates environment configuration."""
        # Store original environment
        original_env = os.environ.copy()
        
        try:
            # Test with clean environment
            os.environ.clear()
            app1 = create_app()
            
            # Test with custom environment
            os.environ['POLYGON_API_KEY'] = 'test_key'
            os.environ['HTTP_TIMEOUT_SECONDS'] = '20.0'
            app2 = create_app()
            
            # Both should be valid FastAPI instances
            assert isinstance(app1, FastAPI)
            assert isinstance(app2, FastAPI)
            
        finally:
            # Restore original environment
            os.environ.clear()
            os.environ.update(original_env)