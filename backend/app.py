"""
backend/app.py
----------------
Flask API + static file server for PakWheelsCarPriceAnalyser.

Run from the project root:
    python backend/app.py

Endpoints:
    GET  /api/cars           -> filtered list of scraped cars
    GET  /api/filters        -> distinct provinces / cities / makes / models for dropdowns
    POST /api/scrape         -> kicks off a live scrape in a background thread
    GET  /api/scrape/status  -> poll while a scrape is running
    GET  /                   -> serves frontend/index.html (and its assets)
"""

import os
import sys
import threading

from flask import Flask, jsonify, request, send_from_directory

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import init_db, get_session
from database.models import Car
from scraper.scraper import run_scrape

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")

# In-memory scrape status shared across requests (fine for a single-worker dev server)
scrape_state = {"running": False, "last_result": None, "error": None}


# --------------------------------------------------------------------------- #
# Frontend
# --------------------------------------------------------------------------- #

@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #

@app.route("/api/cars")
def get_cars():
    session = get_session()
    try:
        query = session.query(Car)

        province = request.args.get("province")
        city = request.args.get("city")
        transmission = request.args.get("transmission")  # Manual / Automatic
        make = request.args.get("make")
        model_name = request.args.get("model")
        year_min = request.args.get("year_min", type=int)
        year_max = request.args.get("year_max", type=int)
        price_min = request.args.get("price_min", type=float)
        price_max = request.args.get("price_max", type=float)

        if province:
            query = query.filter(Car.province == province)
        if city:
            query = query.filter(Car.registration_city == city)
        if transmission:
            query = query.filter(Car.transmission == transmission)
        if make:
            query = query.filter(Car.make.ilike(f"%{make}%"))
        if model_name:
            query = query.filter(Car.model_name.ilike(f"%{model_name}%"))
        if year_min is not None:
            query = query.filter(Car.year >= year_min)
        if year_max is not None:
            query = query.filter(Car.year <= year_max)
        if price_min is not None:
            query = query.filter(Car.price >= price_min)
        if price_max is not None:
            query = query.filter(Car.price <= price_max)

        query = query.order_by(Car.scraped_at.desc()).limit(500)
        cars = [c.to_dict() for c in query.all()]
        return jsonify({"count": len(cars), "results": cars})
    finally:
        session.close()


@app.route("/api/filters")
def get_filters():
    session = get_session()
    try:
        provinces = [r[0] for r in session.query(Car.province).distinct() if r[0]]
        cities = [r[0] for r in session.query(Car.registration_city).distinct() if r[0]]
        makes = [r[0] for r in session.query(Car.make).distinct() if r[0]]
        models = [r[0] for r in session.query(Car.model_name).distinct() if r[0]]
        return jsonify({
            "provinces": sorted(provinces),
            "cities": sorted(cities),
            "makes": sorted(makes),
            "models": sorted(models),
            "transmissions": ["Manual", "Automatic"],
        })
    finally:
        session.close()


def _background_scrape(max_listings: int):
    scrape_state["running"] = True
    scrape_state["error"] = None
    try:
        result = run_scrape(max_listings=max_listings)
        scrape_state["last_result"] = result
    except Exception as exc:  # noqa: BLE001
        scrape_state["error"] = str(exc)
    finally:
        scrape_state["running"] = False


@app.route("/api/scrape", methods=["POST"])
def trigger_scrape():
    if scrape_state["running"]:
        return jsonify({"status": "already_running"}), 409

    max_listings = request.json.get("max", 200) if request.is_json else 200
    thread = threading.Thread(target=_background_scrape, args=(max_listings,), daemon=True)
    thread.start()
    return jsonify({"status": "started"})


@app.route("/api/scrape/status")
def scrape_status():
    return jsonify(scrape_state)


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
