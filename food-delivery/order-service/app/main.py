from fastapi import FastAPI, Depends, HTTPException
# work with DB
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import AsyncSessionLocal
from ...database import AsyncSessionLocal as menu_db
from models import Order, OrderItem
from schemas import OrderCreate, OrderResponse, OrderItemCreate
# other imports
import uuid
import pika
import json
from typing import List

# communication with DB
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session 

app = FastAPI()

# RabbitMQ connection setup
def get_rabbitmq_channel():
    connection = pika.BlockingConnection(pika.ConnectionParameters('rabbitmq'))
    channel = connection.channel()
    channel.exchange_declare(exchange='order_events', exchange_type='fanout')
    return channel

# !!! We need to add other db for Menu Service
# Mock function to get menu items from Menu Service
async def get_menu_item_price(restaurant_id:uuid.UUID, item_ids:List[uuid.UUID], db:AsyncSession=Depends(menu_db))-> dict:
    # need to implement query to menu service or db
    # now return dummy price for demostration
    return {item_ids:10.0 for item_id in item_ids}

#!!! We need to add other db for Menu Service
# -------ROUTES------------
@app.post("/oders/", response_model = OrderResponse)
async def create_order(order_data:OrderCreate, db:AsyncSession=Depends(get_db)):
    async with db.begin():
        # get RabbitMQ channel
        channel=get_rabbitmq_channel()

        #create Oreder
        order = Order(
            id=uuid.uuid4(),
            user_id = order_data.user_id,
            restaurant_id = order_data.restaurant_id,
            status="created"
        )
        db.add(order)
        await db.flush() #Flush to get the order ID for OrderItems

        #Get List[menu_items] from order_data
        item_ids = [item.menu_item_id for item in order_data.items]
        # call prices from Menu service function
        menu_prices = await get_menu_item_price(order_data.restaurant_id, item_ids, db)

        # calcualte total amout for order
        total_amount = 0.0
        # list of menu items in Order
        order_items = []

        # loop through order list [menu_items]
        for item in order_data.items:
            if item.menu_item_id not in menu_prices:
                raise HTTPException(status_code=400, detail=f"Menu item {item.menu_item_id}")
            
            item_price = menu_prices[item.menu_item_id]
            total_amount += item_price*item.quantity

            # creating order_item then add it to order_items list
            order_item = OrderItem(
                id=uuid.uuid4(),
                order_id=order.id,
                menu_item_id=item.menu_item_id,
                quantity = item.quantity,
                price = item_price
            )

            order_items.append(order_item)
        
        # Add all order_items to the session
        db.add_all(order_items)

        # Update order with calculated total
        order.total_amount = total_amount

        # Publish order_created event
        channel.basic_publish(
            exchange="order_events",
            routing_key='',
            body=json.dumps(
                {
                    "event_type":"order_created",
                    "order_id":str(order.id),
                    "user_id":str(order_data.user_id),
                    "restaurant_id":str(order_data.restaurant_id),
                    "amount":total_amount,
                    "items":[{
                        "menu_items_id":str(item.menu_item_id),
                        "quantity":item.quantity,
                        "price":menu_prices[item.menu_item_id]
                    } for item in order_data.items]

                }
            )
        )

        await db.commit()

        return OrderResponse(
            id = order.id,
            user_id=order.user_id,
            restaurant_id = order.restaurant_id,
            status=order.status,
            total_amount=total_amount
            
        )
