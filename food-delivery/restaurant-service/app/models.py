from sqlalchemy import Column, String, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from database import Base
import uuid

#Menu items will be accessed via API calls to Menu Service

class Restaurant(Base):
    __tablename__ = "restaurants"

    id = Column(UUID(as_uuid=True), primary_key = True, default=uuid)
    name = Column(String(100), nullable = False)
    address = Column(String(150), nullable=False)
    cuisine_type = Column(String(50), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    def __repr__(self):
        return f"<Restaurant(id={self.id}, name ='{self.name}')>"

