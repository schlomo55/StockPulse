from __future__ import annotations
from datetime import date, timedelta, datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Query

from app.models.Stock import Stock
from app.models.PurchaseRequest import PurchaseRequest
from app.services.StockService import StockService

router = APIRouter(prefix="/stock", tags=["stock"])


class StockController:
    """HTTP handlers for stock endpoints."""

    def __init__(self, service: StockService):
        """Initialize the StockController with a StockService dependency.
        
        Args:
            service: The StockService instance to handle business logic for stock operations.
        """
        self._service = service

    def _get_last_trading_day(self) -> str:
        """Get the most recent trading day before today.
        
        Markets are typically closed on weekends (Saturday and Sunday).
        This method finds the most recent weekday.
        
        Returns:
            str: Date string in YYYY-MM-DD format for the last trading day.
        """
        current_date = date.today()
        
        # Go back one day at a time until we find a weekday
        while True:
            current_date -= timedelta(days=1)
            # Monday = 0, Sunday = 6
            if current_date.weekday() < 5:  # Monday-Friday are 0-4
                return current_date.isoformat()
        
        # This should never be reached, but just in case
        return (date.today() - timedelta(days=1)).isoformat()

    def register(self, router: APIRouter) -> None:
        """Register stock-related routes with the provided FastAPI router.
        
        Args:
            router: The FastAPI APIRouter instance to register the stock endpoints with.
        """
        @router.get("/{symbol}", response_model=Stock)
        async def get_stock(
            symbol: str,
            date_param: Optional[str] = Query(None, alias="date", description="Date in YYYY-MM-DD format. If not provided, uses the last market trading day.")
        ):
            try:
                # Use provided date or default to last trading day
                if date_param:
                    # Validate date format
                    try:
                        datetime.strptime(date_param, "%Y-%m-%d")
                        target_date = date_param
                    except ValueError:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid date format. Please use YYYY-MM-DD format."
                        )
                else:
                    target_date = self._get_last_trading_day()
                
                return await self._service.get_stock(symbol, target_date)
            except ValueError as e:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
            except RuntimeError as e:
                # Map upstream failures to Bad Gateway
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))

        @router.post("/{symbol}", status_code=status.HTTP_201_CREATED)
        async def add_amount(symbol: str, req: PurchaseRequest):
            try:
                final_amount = self._service.add_amount(symbol, req.amount)
                action = "LONG" if final_amount > 0 else "SHORT" if final_amount < 0 else "NEUTRAL"
                operation = "added to" if req.amount > 0 else "subtracted from" if req.amount < 0 else "set to"
                return {
                    "message": f"{abs(req.amount)} units of stock {symbol.upper()} were {operation} your stock record",
                    "final_amount": final_amount,
                    "action": action
                }
            except Exception as e:
                # Handle any unexpected errors from the service layer
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to update stock amount: {str(e)}"
                )