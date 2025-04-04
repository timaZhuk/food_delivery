from pydantic import BaseModel
import uuid

class PaymentRequest(BaseModel):
    order_id:uuid.UUID
    amount:int
    payment_method:str # "visa" or "paypal"
    card_token: str = None # For Visa
    paypal_order_id: str = None # For PayPal

class PaymentResponse(BaseModel):
    payment_id:str
    status: str
    order_id: uuid.UUID


