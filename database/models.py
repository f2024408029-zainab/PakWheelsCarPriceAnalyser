from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Car(Base):
    __tablename__ = "cars"

    id = Column(Integer, primary_key=True, autoincrement=True)

    title = Column(String(255), nullable=False)
    make = Column(String(100), index=True)
    model_name = Column(String(100), index=True)

    price = Column(Float, index=True)
    year = Column(Integer, index=True)
    mileage = Column(Integer)
    engine_capacity = Column(Integer)

    fuel_type = Column(String(50))
    transmission = Column(String(50), index=True)
    registration_city = Column(String(100), index=True)
    province = Column(String(100), index=True)

    listing_url = Column(String(500), nullable=False)
    image_url = Column(String(500))
    posted_date = Column(String(100))
    scraped_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("listing_url", name="uq_car_listing_url"),
        Index("ix_car_filters", "province", "registration_city", "transmission", "year"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "make": self.make,
            "model_name": self.model_name,
            "price": self.price,
            "year": self.year,
            "mileage": self.mileage,
            "engine_capacity": self.engine_capacity,
            "fuel_type": self.fuel_type,
            "transmission": self.transmission,
            "registration_city": self.registration_city,
            "province": self.province,
            "listing_url": self.listing_url,
            "image_url": self.image_url,
            "posted_date": self.posted_date,
            "scraped_at": self.scraped_at.isoformat() if self.scraped_at else None,
        }