from pydantic import BaseModel
import uuid
from typing import Optional

class MenuItemBase(BaseModel):
    name:str
    description:Optional[str] = None
    price:float
    category:str
    restaurant_id:int

class MenuItemCreate(MenuItemBase):
    is_available = Optional[bool] = True

class MenuItem(MenuItemBase):
    id:uuid.UUID
    is_available:bool

    class Congig:
        orm_mode=True