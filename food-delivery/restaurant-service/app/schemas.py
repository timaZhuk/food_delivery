from pydantic import BaseModel
from typing import Optional
import uuid

# ----------without id--------------------------
class RestaurantBase(BaseModel):
    name:str
    address:str
    cuisine_type:str

# ---------check is active for creation Order-----------------------------
class RestaurantCreate(RestaurantBase):
    is_active:Optional[bool] = True

# Restaurant
class Restaurant(RestaurantBase):
    id:uuid.UUID
    is_active:bool

    class Config:
        orm_mode = True