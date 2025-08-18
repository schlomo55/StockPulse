from typing import Dict
from pydantic import BaseModel, Field, ConfigDict


class Stock(BaseModel):
    """Unified stock model combining Polygon.io OHLC, MarketWatch performance, and user amount."""

    model_config = ConfigDict(populate_by_name=True)

    afterHours: float = Field(..., description="After-hours price")
    close: float = Field(..., description="Close price")
    from_: str = Field(..., alias="from", description="Date string YYYY-MM-DD")
    high: float
    low: float
    open: float
    preMarket: float
    status: str
    symbol: str
    volume: int
    performance: Dict[str, str]
    amount: int = 0