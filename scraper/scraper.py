import requests
from bs4 import BeautifulSoup
import re
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.models import engine, Car, init_db
from sqlalchemy.orm import Session

BASE_URL = "https://www.pakwheels.com/used-cars/search/-/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# UPDATED: Province mapping with Islamabad, AJK, Gilgit and Tribal support
PROVINCE_MAPPING = {
    "punjab": ["lahore", "faisalabad", "rawalpindi", "multan", "gujranwala", "sialkot", "bahawalpur", "sargodha", "rahim yar khan", "gujrat", "murree", "sheikhupura", "sahiwal", "jhelum"],
    "sindh": ["karachi", "hyderabad", "sukkur", "larkana", "nawabshah", "mirpur khas"],
    "kpk": ["peshawar", "abbottabad", "mardan", "mingora", "kohat", "bannu", "swat", "chitral"],
    "balochistan": ["quetta", "gwadar", "khuzdar", "chaman", "sibi"],
    "islamabad": ["islamabad"],
    "azad kashmir": ["muzaffarabad", "mirpur", "rawalakot", "kotli", "bhimber", "bagh"],
    "gilgit baltistan": ["gilgit", "skardu", "hunza", "diamer"]
}

def parse_clean_price(price_str):
    try:
        cleaned = price_str.lower().replace("pkr", "").replace(",", "").strip()
        numbers = re.findall(r"[-+]?\d*\.\d+|\d+", cleaned)
        if not numbers:
            return 0
        val = float(numbers[0])
        if "lac" in cleaned:
            return int(val * 100000)
        if "crore" in cleaned:
            return int(val * 10000000)
        return int(val)
    except:
        return 0

def extract_year_from_title(title_str):
    match = re.search(r'\b(19\d\d|20\d\d)\b', title_str)
    return int(match.group(0)) if match else 2022

def determine_province(city_str):
    city_clean = city_str.lower().strip()
    for province, cities in PROVINCE_MAPPING.items():
        if city_clean in cities:
            return province.title()
    return "Other"

def scrape_and_store_live(pages=2):
    """
    Scrapes live dynamic records directly from PakWheels and saves immediately to the DB.
    """
    init_db()  
    total_inserted = 0
    
    with Session(engine) as session:
        for page in range(1, pages + 1):
            try:
                url = f"{BASE_URL}?page={page}"
                response = requests.get(url, headers=HEADERS, timeout=10)
                
                if response.status_code != 200:
                    print(f"[WARNING] Page {page} returned status code {response.status_code}")
                    continue
                
                soup = BeautifulSoup(response.text, "html.parser")
                listings = soup.find_all("li", class_="classified-listing")
                
                for item in listings:
                    try:
                        # 1. Title Extraction
                        title_elem = item.find("a", class_="car-name")
                        if not title_elem:
                            continue
                        title = title_elem.get_text(strip=True)
                        
                        # 2. Price Extraction
                        price_details_elem = item.find("div", class_="price-details")
                        if not price_details_elem:
                            continue
                        price_raw = price_details_elem.get_text(strip=True)
                        clean_price = parse_clean_price(price_raw)
                        
                        # 3. Location/City Extraction
                        city_elem = item.find("ul", class_="search-vehicle-info-2")
                        city = "Unknown"
                        if city_elem:
                            city_li = city_elem.find("li")
                            if city_li:
                                city = city_li.get_text(strip=True)
                        
                        # 4. Extract Specifications
                        specs_list = item.find("ul", class_="search-vehicle-info")
                        year = extract_year_from_title(title)
                        mileage = 0
                        transmission = "Manual"  
                        engine_capacity = "1000 cc" 
                        
                        if specs_list:
                            lis = specs_list.find_all("li")
                            if len(lis) >= 2:
                                mileage_str = lis[1].get_text(strip=True).replace("km", "").replace(",", "").strip()
                                try:
                                    mileage = int(mileage_str)
                                except:
                                    mileage = 0
                            if len(lis) >= 4:
                                transmission = lis[3].get_text(strip=True)
                            if len(lis) >= 5:
                                engine_capacity = lis[4].get_text(strip=True)

                        # 5. Extract Details for Make and Model
                        words = title.split()
                        make = words[0] if len(words) > 0 else "Unknown"
                        model = words[1] if len(words) > 1 else "Car"
                        province = determine_province(city)
                        
                        # Prevent Duplicates checking both title, price, and city
                        exists = session.query(Car).filter(
                            Car.title == title, 
                            Car.price == clean_price, 
                            Car.city == city
                        ).first()
                        
                        if exists:
                            continue
                            
                        car_record = Car(
                            title=title, 
                            make=make, 
                            model=model,
                            price=clean_price, 
                            year=year, 
                            city=city, 
                            province=province,
                            mileage=mileage,
                            transmission=transmission,
                            engine_capacity=engine_capacity
                        )
                        session.add(car_record)
                        total_inserted += 1
                        
                    except Exception as item_err:
                        continue
                        
                session.commit()
                print(f"[INFO] Successfully processed page {page}.")
            except Exception as page_err:
                print(f"[ERROR] Failed processing page {page}: {page_err}")
                continue
                
    print(f"[SUCCESS] Scraper executed successfully. Added {total_inserted} new dynamic listings.")
    return total_inserted

if __name__ == "__main__":
    scrape_and_store_live(pages=2)