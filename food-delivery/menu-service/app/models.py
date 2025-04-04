from sqlalchemy import Column, String, Boolean, Float
from sqlalchemy.dialects.postgresql import UUID
import uuid
from ...database import Base

class ManuItem(Base):
    __tablename__ = 'menu_items'

    id = Column(UUID(as_uuid=True), primary_key = True, default=uuid)
    restaurant_id = Column(UUID(as_uuid=True), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(String(255))
    price = Column(Float, nullable=False)
    category = Column(String(50), nullable=False)
    is_available = Column(Boolean, default=True, nullable=False)

    def __repr__(self):
        return f"<MenuItem(id={self.id}, name = '{self.name}', restaurant_id={self.restaurant_id})>"
    
    