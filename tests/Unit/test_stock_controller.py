"""Unit tests for StockController class."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException, APIRouter
from fastapi.testclient import TestClient
from app.api.controllers.StockController import StockController
from app.services.StockService import StockService
from app.models.Stock import Stock
from app.models.PurchaseRequest import PurchaseRequest
from datetime import date, timedelta


class TestStockController:
    """Test suite for StockController functionality."""

    def _get_last_trading_day(self) -> str:
        """Get the most recent trading day before today (helper for tests)."""
        current_date = date.today()
        
        # Go back one day at a time until we find a weekday
        while True:
            current_date -= timedelta(days=1)
            # Monday = 0, Sunday = 6
            if current_date.weekday() < 5:  # Monday-Friday are 0-4
                return current_date.isoformat()

    @pytest.fixture
    def mock_service(self):
        """Create a mock StockService for testing."""
        return MagicMock(spec=StockService)

    @pytest.fixture
    def controller(self, mock_service):
        """Create a StockController instance for testing."""
        return StockController(service=mock_service)

    @pytest.fixture
    def sample_stock(self):
        """Sample Stock model for testing."""
        return Stock(
            afterHours=151.0,
            close=152.0,
            from_="2023-01-01",
            high=155.0,
            low=148.0,
            open=150.0,
            preMarket=149.0,
            status="OK",
            symbol="AAPL",
            volume=1000000,
            performance={"5 Day": "+2.5%", "YTD": "+15.7%"},
            amount=100
        )

    @pytest.fixture
    def test_app(self, controller):
        """Create a test FastAPI app with the controller routes."""
        from fastapi import FastAPI
        app = FastAPI()
        router = APIRouter(prefix="/stock", tags=["stock"])
        controller.register(router)
        app.include_router(router)
        return app

    @pytest.fixture
    def client(self, test_app):
        """Create a test client for the FastAPI app."""
        return TestClient(test_app)

    def test_initialization_sets_correct_attributes(self, mock_service):
        """Test that initialization sets service attribute correctly."""
        controller = StockController(service=mock_service)
        assert controller._service == mock_service

    @pytest.mark.asyncio
    async def test_get_stock_successful_with_date_param(self, controller, mock_service, sample_stock):
        """Test successful get_stock call with date parameter."""
        mock_service.get_stock = AsyncMock(return_value=sample_stock)
        
        # Create a mock router and register routes
        router = APIRouter()
        controller.register(router)
        
        # Find the get_stock route function
        get_stock_func = None
        for route in router.routes:
            if hasattr(route, 'endpoint') and route.endpoint.__name__ == 'get_stock':
                get_stock_func = route.endpoint
                break
        
        assert get_stock_func is not None
        
        # Test with date parameter
        result = await get_stock_func(symbol="AAPL", date_param="2023-01-01")
        
        assert result == sample_stock
        mock_service.get_stock.assert_called_once_with("AAPL", "2023-01-01")

    @pytest.mark.asyncio
    async def test_get_stock_successful_without_date_uses_last_trading_day(self, controller, mock_service, sample_stock):
        """Test get_stock without date parameter uses the last trading day."""
        mock_service.get_stock = AsyncMock(return_value=sample_stock)
        
        router = APIRouter()
        controller.register(router)
        
        get_stock_func = None
        for route in router.routes:
            if hasattr(route, 'endpoint') and route.endpoint.__name__ == 'get_stock':
                get_stock_func = route.endpoint
                break
        
        result = await get_stock_func(symbol="AAPL", date_param=None)
        
        # Should use last trading day
        expected_date = controller._get_last_trading_day()
        mock_service.get_stock.assert_called_once_with("AAPL", expected_date)

    @pytest.mark.asyncio
    async def test_get_stock_invalid_date_format_raises_400(self, controller, mock_service):
        """Test that invalid date format raises 400 Bad Request."""
        router = APIRouter()
        controller.register(router)
        
        get_stock_func = None
        for route in router.routes:
            if hasattr(route, 'endpoint') and route.endpoint.__name__ == 'get_stock':
                get_stock_func = route.endpoint
                break
        
        # Test various invalid date formats that will actually fail strptime
        invalid_dates = [
            "01-01-2023",    # Wrong format
            "2023/01/01",    # Wrong separator
            "invalid-date",  # Not a date
            "2023-13-01",    # Invalid month
            "2023-01-32",    # Invalid day
            "2023-1",        # Incomplete date
            "not-a-date",    # Invalid text
        ]
        
        for invalid_date in invalid_dates:
            with pytest.raises(HTTPException) as exc_info:
                await get_stock_func(symbol="AAPL", date_param=invalid_date)
            
            assert exc_info.value.status_code == 400
            assert "Invalid date format" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_stock_service_value_error_raises_404(self, controller, mock_service):
        """Test that service ValueError raises 404 Not Found."""
        mock_service.get_stock = AsyncMock(side_effect=ValueError("Symbol not found"))
        
        router = APIRouter()
        controller.register(router)
        
        get_stock_func = None
        for route in router.routes:
            if hasattr(route, 'endpoint') and route.endpoint.__name__ == 'get_stock':
                get_stock_func = route.endpoint
                break
        
        with pytest.raises(HTTPException) as exc_info:
            await get_stock_func(symbol="INVALID", date_param="2023-01-01")
        
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Symbol not found"

    @pytest.mark.asyncio
    async def test_get_stock_service_runtime_error_raises_502(self, controller, mock_service):
        """Test that service RuntimeError raises 502 Bad Gateway."""
        mock_service.get_stock = AsyncMock(side_effect=RuntimeError("Upstream API failure"))
        
        router = APIRouter()
        controller.register(router)
        
        get_stock_func = None
        for route in router.routes:
            if hasattr(route, 'endpoint') and route.endpoint.__name__ == 'get_stock':
                get_stock_func = route.endpoint
                break
        
        with pytest.raises(HTTPException) as exc_info:
            await get_stock_func(symbol="AAPL", date_param="2023-01-01")
        
        assert exc_info.value.status_code == 502
        assert exc_info.value.detail == "Upstream API failure"

    @pytest.mark.asyncio
    async def test_add_amount_successful(self, controller, mock_service):
        """Test successful add_amount call."""
        mock_service.add_amount.return_value = 150
        
        router = APIRouter()
        controller.register(router)
        
        add_amount_func = None
        for route in router.routes:
            if hasattr(route, 'endpoint') and route.endpoint.__name__ == 'add_amount':
                add_amount_func = route.endpoint
                break
        
        assert add_amount_func is not None
        
        request = PurchaseRequest(amount=50)
        result = await add_amount_func(symbol="AAPL", req=request)
        
        expected_response = {
            "message": "50 units of stock AAPL were added to your stock record",
            "final_amount": 150,
            "action": "LONG"
        }
        assert result == expected_response
        mock_service.add_amount.assert_called_once_with("AAPL", 50)

    @pytest.mark.asyncio
    async def test_add_amount_symbol_case_handling(self, controller, mock_service):
        """Test that add_amount handles symbol case correctly."""
        mock_service.add_amount.return_value = 75
        
        router = APIRouter()
        controller.register(router)
        
        add_amount_func = None
        for route in router.routes:
            if hasattr(route, 'endpoint') and route.endpoint.__name__ == 'add_amount':
                add_amount_func = route.endpoint
                break
        
        request = PurchaseRequest(amount=25)
        result = await add_amount_func(symbol="aapl", req=request)
        
        # Response should show uppercase symbol
        expected_response = {
            "message": "25 units of stock AAPL were added to your stock record",
            "final_amount": 75,
            "action": "LONG"
        }
        assert result == expected_response
        mock_service.add_amount.assert_called_once_with("aapl", 25)

    # Integration tests using TestClient
    def test_get_stock_endpoint_integration_with_date(self, client, mock_service, sample_stock):
        """Test get_stock endpoint integration with date parameter."""
        mock_service.get_stock = AsyncMock(return_value=sample_stock)
        
        response = client.get("/stock/AAPL?date=2023-01-01")
        
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "AAPL"
        assert data["close"] == 152.0
        assert data["amount"] == 100

    def test_get_stock_endpoint_integration_without_date(self, client, mock_service, sample_stock):
        """Test get_stock endpoint integration without date parameter."""
        mock_service.get_stock = AsyncMock(return_value=sample_stock)
        
        response = client.get("/stock/AAPL")
        
        assert response.status_code == 200
        # Should use last trading day
        mock_service.get_stock.assert_called_once()
        call_args = mock_service.get_stock.call_args
        assert call_args[0][0] == "AAPL"  # symbol
        assert call_args[0][1] == self._get_last_trading_day()  # date

    def test_get_stock_endpoint_404_on_value_error(self, client, mock_service):
        """Test get_stock endpoint returns 404 on service ValueError."""
        mock_service.get_stock = AsyncMock(side_effect=ValueError("Symbol not found"))
        
        response = client.get("/stock/INVALID?date=2023-01-01")
        
        assert response.status_code == 404
        assert response.json()["detail"] == "Symbol not found"

    def test_get_stock_endpoint_502_on_runtime_error(self, client, mock_service):
        """Test get_stock endpoint returns 502 on service RuntimeError."""
        mock_service.get_stock = AsyncMock(side_effect=RuntimeError("API failure"))
        
        response = client.get("/stock/AAPL?date=2023-01-01")
        
        assert response.status_code == 502
        assert response.json()["detail"] == "API failure"

    def test_get_stock_endpoint_400_on_invalid_date(self, client, mock_service):
        """Test get_stock endpoint returns 400 on invalid date format."""
        response = client.get("/stock/AAPL?date=invalid-date")
        
        assert response.status_code == 400
        assert "Invalid date format" in response.json()["detail"]

    def test_add_amount_endpoint_integration(self, client, mock_service):
        """Test add_amount endpoint integration."""
        mock_service.add_amount.return_value = 125
        
        response = client.post("/stock/AAPL", json={"amount": 25})
        
        assert response.status_code == 201
        data = response.json()
        assert data["message"] == "25 units of stock AAPL were added to your stock record"
        assert data["final_amount"] == 125
        assert data["action"] == "LONG"
        mock_service.add_amount.assert_called_once_with("AAPL", 25)

    def test_add_amount_endpoint_negative_amount_short_position(self, client, mock_service):
        """Test add_amount endpoint with negative amount resulting in SHORT position."""
        mock_service.add_amount.return_value = -10  # Final amount is negative
        
        response = client.post("/stock/AAPL", json={"amount": -10})
        
        assert response.status_code == 201
        data = response.json()
        assert data["message"] == "10 units of stock AAPL were subtracted from your stock record"
        assert data["final_amount"] == -10
        assert data["action"] == "SHORT"
        mock_service.add_amount.assert_called_once_with("AAPL", -10)

    def test_add_amount_endpoint_validation_missing_amount(self, client, mock_service):
        """Test add_amount endpoint validation with missing amount."""
        response = client.post("/stock/AAPL", json={})
        
        assert response.status_code == 422  # Validation error

    def test_add_amount_endpoint_validation_invalid_amount_type(self, client, mock_service):
        """Test add_amount endpoint validation with invalid amount type."""
        response = client.post("/stock/AAPL", json={"amount": "not_a_number"})
        
        assert response.status_code == 422  # Validation error

    def test_add_amount_endpoint_zero_amount_allowed(self, client, mock_service):
        """Test add_amount endpoint allows zero amount."""
        mock_service.add_amount.return_value = 100
        
        response = client.post("/stock/AAPL", json={"amount": 0})
        
        assert response.status_code == 201
        data = response.json()
        assert data["message"] == "0 units of stock AAPL were set to your stock record"
        assert data["final_amount"] == 100
        assert data["action"] == "LONG"
        mock_service.add_amount.assert_called_once_with("AAPL", 0)

    def test_add_amount_endpoint_neutral_position(self, client, mock_service):
        """Test add_amount endpoint with zero final amount resulting in NEUTRAL position."""
        mock_service.add_amount.return_value = 0  # Final amount is zero
        
        response = client.post("/stock/AAPL", json={"amount": -50})
        
        assert response.status_code == 201
        data = response.json()
        assert data["message"] == "50 units of stock AAPL were subtracted from your stock record"
        assert data["final_amount"] == 0
        assert data["action"] == "NEUTRAL"
        mock_service.add_amount.assert_called_once_with("AAPL", -50)

    def test_add_amount_endpoint_negative_to_positive_transition(self, client, mock_service):
        """Test add_amount with negative amount but positive final result (SHORT to LONG)."""
        mock_service.add_amount.return_value = 25  # Final amount is positive
        
        response = client.post("/stock/AAPL", json={"amount": -10})
        
        assert response.status_code == 201
        data = response.json()
        assert data["message"] == "10 units of stock AAPL were subtracted from your stock record"
        assert data["final_amount"] == 25
        assert data["action"] == "LONG"  # Even though we subtracted, final position is LONG
        mock_service.add_amount.assert_called_once_with("AAPL", -10)

    def test_add_amount_endpoint_positive_to_negative_transition(self, client, mock_service):
        """Test add_amount with positive amount but negative final result (LONG to SHORT)."""
        mock_service.add_amount.return_value = -15  # Final amount is negative
        
        response = client.post("/stock/AAPL", json={"amount": 10})
        
        assert response.status_code == 201
        data = response.json()
        assert data["message"] == "10 units of stock AAPL were added to your stock record"
        assert data["final_amount"] == -15
        assert data["action"] == "SHORT"  # Even though we added, final position is SHORT
        mock_service.add_amount.assert_called_once_with("AAPL", 10)

    def test_add_amount_endpoint_large_positive_amount(self, client, mock_service):
        """Test add_amount endpoint with large positive amount."""
        mock_service.add_amount.return_value = 1000000
        
        response = client.post("/stock/AAPL", json={"amount": 999999})
        
        assert response.status_code == 201
        data = response.json()
        assert data["message"] == "999999 units of stock AAPL were added to your stock record"
        assert data["final_amount"] == 1000000
        assert data["action"] == "LONG"
        mock_service.add_amount.assert_called_once_with("AAPL", 999999)

    def test_add_amount_endpoint_large_negative_amount(self, client, mock_service):
        """Test add_amount endpoint with large negative amount."""
        mock_service.add_amount.return_value = -500000
        
        response = client.post("/stock/AAPL", json={"amount": -500000})
        
        assert response.status_code == 201
        data = response.json()
        assert data["message"] == "500000 units of stock AAPL were subtracted from your stock record"
        assert data["final_amount"] == -500000
        assert data["action"] == "SHORT"
        mock_service.add_amount.assert_called_once_with("AAPL", -500000)

    def test_route_registration_creates_correct_routes(self, controller):
        """Test that route registration creates the expected routes."""
        router = APIRouter()
        controller.register(router)
        
        # Should have 2 routes: GET and POST
        assert len(router.routes) == 2
        
        # Check route paths and methods
        get_route = None
        post_route = None
        
        for route in router.routes:
            if hasattr(route, 'methods'):
                if 'GET' in route.methods:
                    get_route = route
                elif 'POST' in route.methods:
                    post_route = route
        
        assert get_route is not None
        assert post_route is not None
        
        # Check path patterns (FastAPI uses path_regex)
        assert "symbol" in str(get_route.path)
        assert "symbol" in str(post_route.path)

    def test_get_stock_endpoint_case_insensitive_symbol(self, client, mock_service, sample_stock):
        """Test get_stock endpoint with different symbol cases."""
        mock_service.get_stock = AsyncMock(return_value=sample_stock)
        
        symbols = ["aapl", "AAPL", "ApPl", "googl", "MSFT"]
        
        for symbol in symbols:
            response = client.get(f"/stock/{symbol}?date=2023-01-01")
            assert response.status_code == 200
            
            # Verify service was called with exact symbol
            mock_service.get_stock.assert_called_with(symbol, "2023-01-01")

    def test_add_amount_endpoint_case_insensitive_symbol(self, client, mock_service):
        """Test add_amount endpoint with different symbol cases."""
        mock_service.add_amount.return_value = 50
        
        symbols = ["aapl", "AAPL", "ApPl", "googl", "MSFT"]
        
        for symbol in symbols:
            response = client.post(f"/stock/{symbol}", json={"amount": 10})
            assert response.status_code == 201
            
            # Check response message uses uppercase
            data = response.json()
            assert symbol.upper() in data["message"]
            
            # Verify service was called with exact symbol
            mock_service.add_amount.assert_called_with(symbol, 10)

    def test_date_validation_accepts_valid_dates(self, client, mock_service, sample_stock):
        """Test that date validation accepts various valid date formats."""
        mock_service.get_stock = AsyncMock(return_value=sample_stock)
        
        valid_dates = [
            "2023-01-01",
            "2023-12-31", 
            "2024-02-29",  # Leap year
            "2000-01-01",
            "2099-12-31"
        ]
        
        for valid_date in valid_dates:
            response = client.get(f"/stock/AAPL?date={valid_date}")
            assert response.status_code == 200

    def test_date_validation_rejects_invalid_dates(self, client, mock_service):
        """Test that date validation rejects invalid date formats."""
        # Mock service should return proper Stock object to avoid validation errors
        mock_stock = Stock(
            afterHours=151.0,
            close=152.0,
            from_="2023-01-01",
            high=155.0,
            low=148.0,
            open=150.0,
            preMarket=149.0,
            status="OK",
            symbol="AAPL",
            volume=1000000,
            performance={"YTD": "+15.7%"},
            amount=100
        )
        mock_service.get_stock = AsyncMock(return_value=mock_stock)
        
        invalid_dates = [
            "01-01-2023",    # Wrong format
            "2023/01/01",    # Wrong separator
            "2023-13-01",    # Invalid month
            "2023-01-32",    # Invalid day
            "2023-02-30",    # Invalid date for February
            "not-a-date",    # Not a date at all
            "2023-1",        # Incomplete date
            "invalid-text",  # Invalid text
        ]
        
        for invalid_date in invalid_dates:
            response = client.get(f"/stock/AAPL?date={invalid_date}")
            assert response.status_code == 400

    def test_response_model_validation(self, client, mock_service):
        """Test that response follows the Stock model schema."""
        # Create a stock with all required fields
        stock = Stock(
            afterHours=151.0,
            close=152.0,
            from_="2023-01-01",
            high=155.0,
            low=148.0,
            open=150.0,
            preMarket=149.0,
            status="OK",
            symbol="AAPL",
            volume=1000000,
            performance={"YTD": "+15.7%"},
            amount=100
        )
        mock_service.get_stock = AsyncMock(return_value=stock)
        
        response = client.get("/stock/AAPL?date=2023-01-01")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify all Stock model fields are present
        required_fields = [
            "afterHours", "close", "from", "high", "low", "open",
            "preMarket", "status", "symbol", "volume", "performance", "amount"
        ]
        
        for field in required_fields:
            assert field in data