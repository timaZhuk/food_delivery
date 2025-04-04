from pydantic import BaseModel
import uuid

class Notification(BaseModel):
    order_id:uuid.UUID
    message:str
    notification_type:str  # "payment", "status_update", etc

