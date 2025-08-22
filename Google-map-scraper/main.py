from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import json
from datetime import datetime
import os
from scraper import AdvancedContactExtractor
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

app = FastAPI(title="Google Maps Business Scraper API")

class SearchRequest(BaseModel):
    search_query: str
    max_results: Optional[int] = 20
    visit_websites: Optional[bool] = True

class BusinessData(BaseModel):
    business_name: str
    address: Optional[str]
    phone_no: Optional[str]
    website: Optional[str]
    rating: Optional[float]
    review_count: Optional[int]
    category: Optional[str]
    primary_email: Optional[str]
    secondary_email: Optional[str]
    additional_contacts: Optional[dict]

@app.get("/")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "Google Maps Scraper API"
    }

def get_chrome_options():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-software-rasterizer")

    if os.environ.get("CHROME_BIN"):
        chrome_options.binary_location = os.environ["CHROME_BIN"]

    return chrome_options

@app.get("/test-chrome")
async def test_chrome():
    try:
        chrome_options = get_chrome_options()
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)

        driver.get("https://www.google.com")
        title = driver.title
        driver.quit()

        return {
            "status": "success",
            "chrome_version": driver.capabilities["browserVersion"],
            "page_title": title
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chrome test failed: {str(e)}")

@app.post("/scrape")
async def scrape_businesses(request: SearchRequest):
    try:
        # Initialize scraper
        scraper = AdvancedContactExtractor(
            search_query=request.search_query,
            max_results=request.max_results,
            visit_websites=request.visit_websites
        )

        # Run extraction
        results = scraper.run_extraction()

        # Format results
        formatted_results = []
        for business_data in results:
            if business_data:
                formatted_data = {
                    "business_name": business_data.get("business_name", ""),
                    "address": business_data.get("address"),
                    "phone_no": business_data.get("phone_no"),
                    "website": business_data.get("website"),
                    "rating": business_data.get("rating"),
                    "review_count": business_data.get("review_count"),
                    "category": business_data.get("category"),
                    "primary_email": business_data.get("primary_email"),
                    "secondary_email": business_data.get("secondary_email"),
                    "additional_contacts": json.loads(business_data.get("additional_contacts", "{}"))
                }
                formatted_results.append(formatted_data)

        return {
            "status": "success",
            "message": f"Found {len(formatted_results)} businesses",
            "data": formatted_results
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
