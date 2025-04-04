from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import stripe 
import paypalrestsdk
import pika
import json
import os
from schemas import PaymentRequest, PaymentResponse
# from database import get_db

app = FastAPI()

# configuration payments providers
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
paypalrestsdk.configure({
    "mode":os.getenv("PAYPAL_MODE", "sandbox"),
    "client_id":os.getenv("PAYPAL_CLIENT_ID"),
    "client_secret":os.getenv("PAYPAL_SECRET")
})

#  RabbitMQ connection
connection = pika.BlockingConnection(pika.ConnectionParameters('rabbitmq'))
channel = connection.channel()
channel.exchange_declare(exchange='payment_events', exchange_type='fanout')

@app.post("/pay/", response_model = PaymentResponse)
async def process_payment(payment:PaymentRequest):
    try:
        if payment.payment_method == "visa":
            # Process Visa payment
            charge = stripe.Charge.crate(
                amount=payment.amount,
                currency="usd",
                source=payment.card_token,
                description=f"Order{payment.order_id}"
            )
            payment_id = charge.id
        elif payment.payment_method == "paypal":
            # Process PayPal payment
            payment_execute = paypalrestsdk.Payment.find(payment.paypal_order_id)
            if payment_execute.execute({"payer_id":payment.paypal_order_id}):
                payment_id = payment_execute.request_id
            else:
                raise HTTPException(status_code=400, detail= payment_execute.error)
        else:
            raise HTTPException(status_code=400, detail="Invalid payment method")
        
        # Publish payment_success event
        channel.basic_publish(
            exchange="payment_events",
            routing_key='',
            body=json.dumps({
                "event_type":"payment_success",
                "order_id":str(payment.order_id),
                "payment_id":payment_id,
                "amount":payment.amount
            })
        )
        return PaymentResponse(
            payment_id=payment_id,
            status="completed",
            order_id=payment.order_id
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))