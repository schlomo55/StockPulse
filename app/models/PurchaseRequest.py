from __future__ import annotations
from pydantic import BaseModel, Field


class PurchaseRequest(BaseModel):
    """Request body for adding purchased amount.

    Supports both positive (add) and negative (subtract) integer amounts.
    """

    amount: int = Field(..., description="Integer amount (positive to add, negative to subtract)")