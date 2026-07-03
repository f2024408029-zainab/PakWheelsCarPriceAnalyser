import os
from sqlalchemy import create_engine, Column, Integer, String, DateTime, func
from sqlalchemy.orm import declarative_base, Session
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "pakwheels.db")

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
Base = declarative_base()

class Car(Base):
    __tablename__ = "cars"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    make = Column(String, nullable=False)
    model = Column(String, nullable=False)
    price = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    city = Column(String, nullable=False)
    province = Column(String, nullable=False)
    mileage = Column(Integer, nullable=True)
    transmission = Column(String, nullable=True)
    engine_capacity = Column(String, nullable=True)
    scraped_at = Column(DateTime, default=datetime.utcnow)

def init_db():
    Base.metadata.create_all(engine)

def query_filtered_cars(province=None, model=None, year=None):
    with Session(engine) as session:
        q = session.query(Car)
        if province: q = q.filter(Car.province.ilike(province))
        if model: q = q.filter(Car.model.ilike(model))
        if year: q = q.filter(Car.year == int(year))
    return [
               
            {"id": c.id, "title": c.title, "make": c.make, "model": c.model,
             "price": c.price, "year": c.year, "city": c.city, "province": c.province,
             "mileage": c.mileage, "transmission": c.transmission, "engine_capacity": c.engine_capacity}
            for c in q.all()
        ]
        
def evaluate_car_deal(make, model, input_year, user_price):
    with Session(engine) as session:
        avg_price = session.query(func.avg(Car.price)).filter(
            Car.make.ilike(make),
            Car.model.ilike(model),
            Car.year == int(input_year)
        ).scalar()
        if not avg_price:
            return {"status": "Unknown", "message": "Not enough historical market data to evaluate."}
        avg_price = int(avg_price)
        lower_threshold = avg_price * 0.90
        upper_threshold = avg_price * 1.10
        if user_price < lower_threshold:
            deal = "Great Deal (Underpriced)"
        elif user_price > upper_threshold:
            deal = "Overpriced"
        else:
            deal = "Fair Market Price"
        return {
            "status": "Success",
            "market_average": avg_price,
            "your_price": user_price,
            "deal_evaluation": deal
        }

def get_market_dashboard_stats():
    with Session(engine) as session:
        total_cars = session.query(func.count(Car.id)).scalar()
        if total_cars == 0 or total_cars is None:
            return {"error": "Database is empty"}
        min_car = session.query(Car.title, Car.price).order_by(Car.price.asc()).first()
        max_car = session.query(Car.title, Car.price).order_by(Car.price.desc()).first()
        top_brands_raw = session.query(Car.make, func.count(Car.id)).group_by(Car.make).order_by(func.count(Car.id).desc()).limit(3).all()
        top_brands = [{"brand": item[0], "listings": item[1]} for item in top_brands_raw]
        return {
            "total_listings": total_cars,
            "cheapest_car": {"title": min_car[0], "price": min_car[1]} if min_car else None,
            "most_expensive_car": {"title": max_car[0], "price": max_car[1]} if max_car else None,
            "market_share": top_brands
        }
