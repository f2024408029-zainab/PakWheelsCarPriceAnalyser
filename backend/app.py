import os
import sys
import threading
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.models import SessionLocal, init_db, Car, get_filtered_cars, evaluate_car_deal
from scraper.scraper import scrape_and_store_live

app = Flask(
    __name__,
    template_folder="../frontend/templates",
    static_folder="../frontend/static"
)
CORS(app)

# Ensure database tables exist upon application startup
init_db()

@app.route("/")
def home():
    """Renders the main dashboard HTML page"""
    return render_template("index.html")

@app.route("/api/scrape", methods=["POST"])
def trigger_live_scrape():
    """
    Triggers the PakWheels scraper dynamically in a background thread 
    so the web app remains responsive and real-time data keeps appending.
    """
    try:
        data = request.get_json() or {}
        pages = int(data.get("pages", 2))
        
        # Running the scraper inside a thread prevents the page from freezing/timing out
        scraper_thread = threading.Thread(target=scrape_and_store_live, args=(pages,))
        scraper_thread.start()
        
        return jsonify({
            "status": "success",
            "message": f"Live scraping initiated for {pages} pages in the background. Fresh records will sync momentarily."
        }), 202
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/cars", methods=["GET"])
def fetch_filtered_cars():
    """
    API endpoint that returns real-time data from the DB based on 
    user-selected filters (Province, Transmission, Price, Year).
    """
    db = SessionLocal()
    try:
        # Extract query parameters from request URL
        filters = {
            "province": request.args.get("province"),
            "transmission": request.args.get("transmission"),
            "year_from": request.args.get("year_from"),
            "year_to": request.args.get("year_to"),
            "price_min": request.args.get("price_min"),
            "price_max": request.args.get("price_max")
        }
        
        # Get cars matching the query sorted by newest/latest scraped
        cars_list = get_filtered_cars(db, filters)
        
        # Serialize database objects into plain JSON
        result = []
        for car in cars_list:
            result.append({
                "id": car.id,
                "title": car.title,
                "make": car.make,
                "model": car.model,
                "price": car.price,
                "year": car.year,
                "city": car.city,
                "province": car.province,
                "mileage": car.mileage,
                "transmission": car.transmission,
                "engine_capacity": car.engine_capacity,
                "scraped_at": car.scraped_at.strftime("%Y-%m-%d %H:%M:%S")
            })
            
        return jsonify({"status": "success", "count": len(result), "data": result}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()

@app.route("/api/evaluate", methods=["POST"])
def evaluate_manual_input():
    """
    Fair Price Dashboard Endpoint. Evaluates the user's manual inputs 
    against live scraped market averages.
    """
    db = SessionLocal()
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "Missing input data form"}), 400
            
        make = data.get("make", "").strip()
        model = data.get("model", "").strip()
        year = data.get("year")
        user_price = data.get("price")
        mileage = data.get("mileage", 0)
        transmission = data.get("transmission", "Automatic")
        
        if not (make and model and year and user_price):
            return jsonify({"status": "error", "message": "Make, Model, Year, and Price are required fields"}), 400
            
        evaluation = evaluate_car_deal(
            session=db,
            make=make,
            model=model,
            year=year,
            user_price=float(user_price),
            mileage=int(mileage),
            transmission=transmission
        )
        
        return jsonify({"status": "success", "evaluation": evaluation}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()

if __name__ == "__main__":
    app.run(debug=True, port=5000)