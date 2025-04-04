from fastapi import FastAPI, Depends, HTTPException, status
# work with DB
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import AsyncSessionLocal
from ...database import AsyncSessionLocal as menu_db
from models import Order, OrderItem
from schemas import OrderCreate, OrderResponse
# other imports
import uuid
import pika
import json
import httpx
from typing import List
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


app = FastAPI()

# communication with DB
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session 


# RabbitMQ connection setup
def get_rabbitmq_channel():
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(
            host = 'rabbitmq',
            heartbeat=600,
            blocked_connection_timeout=300
        
            ))
        channel = connection.channel()
        channel.exchange_declare(exchange='order_events', exchange_type='topic', durable=True)
        return channel
    except Exception as e:
        logger.error("f RabbitMQ connection failed:{str(e)}")
        raise

#Need to fix. Service URLs (would normally come from config)
MENU_SERVICE_URL = "http://menu-service:8000"
RESTAURANT_SERVICE_URL = "http://restaurant-service:8000"

# Validation Restaurant service
async def validate_restaurant(restauarnt_id:uuid.UUID)->bool:
    # Check if restaurant exist and is active
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{RESTAURANT_SERVICE_URL}/restaurants/{restauarnt_id}",
                timeout=5.0
            )
            if response.status_code == 200:
                restaurant = response.json()
                return restaurant.get('is_active', False)
            return False
    except Exception as e:
        logger.error(f"Restaurant validation failed: {str(e)}")
        return False

async def get_menu_items_with_prices(
        restaurant_id:uuid.UUID,
        item_ids:List[uuid.UUID]
)-> dict:
    # Fetch menu items from Menu Service and return prices
    try:
        async with httpx.AsyncClient() as client:
            # First validate all items belong to this restauarnt
            response = await client.post(
                f"{MENU_SERVICE_URL}/menu/validate-items",
                json ={
                    "restaurant_id":str(restaurant_id),
                    "items_ids":[str(item_id) for item_id in item_ids]
                },
                timeout=5.0
            )
            
            if response.status_code !=200:
                raise HTTPException(
                    status_code = status.HTTP_400_BAD_REQUEST,
                    detail = "Invalid menu items for this restaurant"
                )
            
            # Then get the prices
            response = await client.post(
                f"{MENU_SERVICE_URL}/menu/prices",
                json={"items_ids":[str(item_id) for item_id in item_ids]}

            )

            if response.status_code == 200:
                return response.json()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to fetch menu prices"
            )
    except httpx.RequestError as e:
        logger.error(f"Menu service request failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Menu service unavailable"
        )

# -----  ROUTE---------------







# -------ROUTES------------
@app.post("/oders/", response_model = OrderResponse)
async def create_order(order_data:OrderCreate, db:AsyncSession=Depends(get_db)):

    # Validate restaurant exists and is active
    if not await validate_restaurant(order_data.restaurant_id):
        raise HTTPException(
            status_code = status.HTTP_400_BAD_REQUEST,
            detail="Restaurant not available"
        )
    
    # Get menu items and prices
    item_ids = [item.menu_item_id for item in order_data.items]
    try:
        menu_prices = await get_menu_items_with_prices(order_data.restaurant_id, item_ids)
    except HTTPException as e:
        raise e
    

    

    #create order in transaction
    async with db.begin():

        #create Oreder
        order = Order(
            id=uuid.uuid4(),
            user_id = order_data.user_id,
            restaurant_id = order_data.restaurant_id,
            delivery_address = order_data.delivery_address
            status="created"
        )
        db.add(order)
        await db.flush() #Flush to get the order ID for OrderItems

        

        # calcualte total amout for order
        total_amount = 0.0
        # list of menu items in Order
        order_items = []

        # loop through order list [menu_items]
        for item in order_data.items:
            
            item_price = menu_prices.get(str(item.menu_item_id))
            if item_price is None:
                await db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Price not found for menu item {item.menu_item_id}"
                )
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
        try:
            channel =get_rabbitmq_channel()
            channel.basic_publish(
                exchange="order_events",
                routing_key='order.created',
                body=json.dumps(
                {
                    "event_type":"order_created",
                    "order_id":str(order.id),
                    "user_id":str(order_data.user_id),
                    "restaurant_id":str(order_data.restaurant_id),
                    "amount":total_amount,
                    "timestamp":datetime.utcnow().isoformat(),
                    "items":[{
                        "menu_items_id":str(item.menu_item_id),
                        "quantity":item.quantity,
                        "price":menu_prices[str(item.menu_item_id)]
                    } for item in order_data.items]

                }
            ),
            properties=pika.BasicProperties(
                delivery_mode=2 # Make message persistent
            )
        )
        except Exception as e:
            logger.error(f"Failed to publish order event:{str(e)}")
            # we will proceed with order creation even if event publishing fails

        await db.commit()


        return OrderResponse(
            id = order.id,
            user_id=order.user_id,
            restaurant_id = order.restaurant_id,
            status=order.status,
            total_amount=total_amount,
            created_at = datetime.utcnow()
            
        )
    
@app.on_event("startup")
async def startup_event():
    # Initialize RabbitMQ queues
    try:
        channel = get_rabbitmq_channel()
        channel.queue_declare(queue='payment_processing', durable=True)
        channel.queue_bind(exchange='order_events', queue='payment_processing', routing_key='order.created')
        
        channel.queue_declare(queue='notifications', durable=True)
        channel.queue_bind(exchange='order_events', queue='notifications', routing_key='order.*')
        
        channel.queue_declare(queue='restaurant_orders', durable=True)
        channel.queue_bind(exchange='order_events', queue='restaurant_orders', routing_key='order.created')
        
        logger.info("RabbitMQ queues initialized")
    except Exception as e:
        logger.error(f"Failed to initialize RabbitMQ: {str(e)}")
