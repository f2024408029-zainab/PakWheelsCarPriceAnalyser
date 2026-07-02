import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'database', 'pakwheels.db')}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Car(Base):
    __tablename__ = "cars"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    make = Column(String, nullable=False)        # e.g., Toyota
    model = Column(String, nullable=False)       # e.g., Corolla
    price = Column(Float, nullable=False)        # Saved as clean integer/float
    year = Column(Integer, nullable=False)
    city = Column(String, nullable=False)
    province = Column(String, nullable=False)    # Punjab, Sindh, KPK, AJK, etc.
    mileage = Column(Integer, nullable=False)     # in KM
    transmission = Column(String, nullable=False) # Manual / Automatic
    engine_capacity = Column(String, nullable=False) # e.g., 1300 cc
    scraped_at = Column(DateTime, default=datetime.utcnow) # Track freshness of data

def init_db():
    """Creates tables if they don't exist without destroying data"""
    Base.metadata.create_base(bind=engine)

def get_filtered_cars(session, filters):
    """
    Query database dynamically based on user filters for the real-time webpage.
    """
    query = session.query(Car)
    
    if filters.get("province"):
        query = query.filter(Car.province == filters["province"])
    if filters.get("transmission"):
        query = query.filter(Car.transmission == filters["transmission"])
    if filters.get("year_from"):
        query = query.filter(Car.year >= int(filters["year_from"]))
    if filters.get("year_to"):
        query = query.filter(Car.year <= int(filters["year_to"]))
    if filters.get("price_min"):
        query = query.filter(Car.price >= float(filters["price_min"]))
    if filters.get("price_max"):
        query = query.filter(Car.price <= float(filters["price_max"]))
        
    return query.order_by(Car.scraped_at.desc()).all()

def evaluate_car_deal(session, make, model, year, user_price, mileage, transmission):
    """
    Fair Price Dashboard Algorithm: Calculates avg price for similar live cars 
    and tells the user if their manual entry is a Good, Fair, or Bad deal.
    """
    similar_cars = session.query(Car).filter(
        Car.make. some_match_logic == make, # Handled in API via lowercase/like
        Car.model.ilike(f"%{model}%"),
        Car.year == int(year),
        Car.transmission == transmission
    ).all()
    
    if not similar_cars:
        return {"status": "No live data available for this specific model yet. Keep scraping!"}
        
    total_price = sum(car.price for car in similar_cars)
    avg_price = total_price / len(similar_cars)
    
    # Simple evaluation logic
    price_diff = user_price - avg_price
    percent_diff = (price_diff / avg_price) * 100
    
    if percent_diff < -5:
        deal = "Great Deal! Price is lower than market average."
    elif percent_diff > 5:
        deal = "Overpriced! Higher than current market average."
    else:
        deal = "Fair Price. Aligns perfectly with live market value."
        
    return {
        "market_average": int(avg_price),
        "total_listings_compared": len(similar_cars),
        "status": deal
    }