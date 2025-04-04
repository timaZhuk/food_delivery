from pydantic import BaseModel, Field
from typing import List
import uuid
from datetime import datetime

class OrderItemCreate(BaseModel):
    menu_item_id: uuid.UUID
    quantity: int = Field(gt=0, description="Quantity must be at least 1")

class OrderCreate(BaseModel):
    user_id: uuid.UUID
    restaurant_id: uuid.UUID
    items: List[OrderItemCreate]
    delivery_address: str

class OrderResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    restaurant_id: uuid.UUID
    status: str
    total_amount: int
    created_at: datetime | None = None
    updated_at: datetime | None = None
    
    class Config:
        from_attributes = True  # Orm_mode in Pydantic v2